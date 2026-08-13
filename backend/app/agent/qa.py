"""问答核心：检索知识库 → LLM（支持 function calling 工具调用）→ 答案 + 引用 + 拒答 + 多轮"""
import time

from openai import (
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    OpenAI,
    RateLimitError,
)

from app.config import settings
from app.cost import estimate_cost
from app.knowledge.indexer import VectorIndex
from app.session.store import SessionStore
from app import state
from app.tools.registry import TOOLS, execute_tool

SYSTEM_PROMPT = """你是公司内部 AI 助手「小苏」，负责根据公司文档与内部系统回答员工问题。

规则：
1. 先判断问题类型：制度/文档类问题依据【参考文档】回答，答案里必须用 [1][2] 标注引用来源编号；员工/考勤/订单/时间类问题必须调用对应工具，依据工具结果回答。
2. 文档里找不到答案时，明确回答「文档里没找到相关内容」，绝不编造。
3. 当用户问到员工部门、考勤、销售订单、当前时间，或给出员工编号（如 001）时，必须直接调用 query_employee / query_attendance / query_orders / current_time，不能只说“我可以帮您查询”，也不能从文档里编造答案。
4. 回答用中文，简洁、专业、口语友好；先给结论，再给依据。
5. 如果历史消息里出现过“我可以帮您查询”但没有实际调用工具，那是错误的旧回答；当前问题需要工具时仍必须直接调用，不要沿用历史中的拒答。"""


class LLMUnavailableError(Exception):
    """重试后模型服务仍不可用，调用方应降级返回友好提示。"""


class QaEngine:
    def __init__(self, index: VectorIndex, sessions: SessionStore, client: OpenAI | None = None) -> None:
        self._index = index
        self._sessions = sessions
        self._provided_client = client
        self._active_provider: tuple | None = None
        self._client: OpenAI | None = None
        self._model = ""

    @property
    def model(self) -> str:
        return self._model

    def _ensure_client(self) -> None:
        """按当前激活供应商构建 client；供应商/Key/模型变化时自动重建（运行时切换生效）"""
        p = settings.get_provider(state.current_provider)
        key = (p.api_key, p.base_url, p.model)
        if key != self._active_provider:
            self._active_provider = key
            self._client = self._provided_client or OpenAI(
                api_key=p.api_key or "sk-none",
                base_url=p.base_url,
                timeout=settings.llm_timeout_seconds,
            )
            self._model = p.model

    def _call_llm_once(self, messages: list[dict], **kwargs):
        """单次 LLM 调用：对超时/连接/限流/5xx 做指数退避重试。"""
        last_error: Exception | None = None
        for attempt in range(settings.llm_max_retries + 1):
            try:
                return self._client.chat.completions.create(
                    model=self._model,
                    messages=messages,
                    tools=TOOLS,
                    temperature=0.3,
                    max_tokens=800,
                    **kwargs,
                )
            except (
                APITimeoutError,
                APIConnectionError,
                RateLimitError,
                InternalServerError,
            ) as e:
                last_error = e
                if attempt < settings.llm_max_retries:
                    time.sleep(min(0.3 * (2**attempt), 1.5))
        raise LLMUnavailableError(f"模型服务暂时不可用: {last_error}") from last_error

    def answer(
        self,
        user_id: str,
        session_id: str,
        question: str,
        manual_hits: list[dict] | None = None,
    ) -> dict:
        self._ensure_client()
        hits = self._index.search(question, k=4) if manual_hits is None else manual_hits
        references = [
            {
                "name": h["name"],
                "text": h["text"][:300],
                "doc_id": h["doc_id"],
                "chunk_index": h["chunk_index"],
            }
            for h in hits
        ]

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self._sessions.get_messages(user_id, session_id)
        user_content = question
        if hits:
            context = "\n\n".join(
                f"[{i + 1}] 来源《{h['name']}》第 {h['chunk_index'] + 1} 段：\n{h['text']}"
                for i, h in enumerate(hits)
            )
            user_content = f"【参考文档】\n{context}\n\n【问题】{question}"
        messages.append({"role": "user", "content": user_content})

        answer, used_tool, tools_used, usage = self._call_llm_with_tools(messages)
        self._sessions.append(user_id, session_id, question, answer)

        # 拒答判定：没调工具且模型明确说没找到
        refused = (not used_tool) and any(
            k in answer for k in ("文档里没找到", "没有找到", "无法回答")
        )
        cost = estimate_cost(self._model, usage)
        self._sessions.log_turn(
            user_id=user_id,
            session_id=session_id,
            question=question,
            answer=answer,
            used_tool=used_tool,
            refused=refused,
            provider=state.current_provider,
            usage=usage,
            cost=cost,
            tools_used=tools_used,
        )
        return {
            "answer": answer,
            "references": references,
            "refused": refused,
            "used_tool": used_tool,
            "tools_used": tools_used,
            "usage": usage,
            "cost": cost,
            "provider": state.current_provider,
            "session_id": session_id,
        }

    def answer_stream(
        self,
        user_id: str,
        session_id: str,
        question: str,
        manual_hits: list[dict] | None = None,
    ):
        """流式问答：先检索知识库，再逐字返回模型输出，最后返回完成元数据。"""
        self._ensure_client()
        hits = self._index.search(question, k=4) if manual_hits is None else manual_hits
        references = [
            {
                "name": h["name"],
                "text": h["text"][:300],
                "doc_id": h["doc_id"],
                "chunk_index": h["chunk_index"],
            }
            for h in hits
        ]

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        messages += self._sessions.get_messages(user_id, session_id)
        user_content = question
        if hits:
            context = "\n\n".join(
                f"[{i + 1}] 来源《{h['name']}》第 {h['chunk_index'] + 1} 段：\n{h['text']}"
                for i, h in enumerate(hits)
            )
            user_content = f"【参考文档】\n{context}\n\n【问题】{question}"
        messages.append({"role": "user", "content": user_content})

        result = {
            "answer": "",
            "used_tool": False,
            "tools_used": [],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }
        yield from self._stream_with_tools(messages, result)

        self._sessions.append(user_id, session_id, question, result["answer"])
        refused = (not result["used_tool"]) and any(
            k in result["answer"] for k in ("文档里没找到", "没有找到", "无法回答")
        )
        cost = estimate_cost(self._model, result["usage"])
        self._sessions.log_turn(
            user_id=user_id,
            session_id=session_id,
            question=question,
            answer=result["answer"],
            used_tool=result["used_tool"],
            refused=refused,
            provider=state.current_provider,
            usage=result["usage"],
            cost=cost,
            tools_used=result["tools_used"],
        )
        yield {
            "type": "done",
            "data": {
                "answer": result["answer"],
                "references": references,
                "refused": refused,
                "used_tool": result["used_tool"],
                "tools_used": result["tools_used"],
                "usage": result["usage"],
                "cost": cost,
                "provider": state.current_provider,
                "session_id": session_id,
            },
        }

    def _stream_with_tools(self, messages: list[dict], result: dict):
        """function calling + 流式输出循环：逐段产出模型内容，工具调用结果回传给模型。"""
        for _ in range(5):
            stream = self._call_llm_once(
                messages,
                stream=True,
                stream_options={"include_usage": True},
            )
            text_parts: list[str] = []
            tool_calls: dict[int, dict] = {}
            usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
            for chunk in stream:
                u = getattr(chunk, "usage", None)
                if u is not None:
                    usage["prompt_tokens"] += getattr(u, "prompt_tokens", 0) or 0
                    usage["completion_tokens"] += getattr(u, "completion_tokens", 0) or 0
                    usage["total_tokens"] += getattr(u, "total_tokens", 0) or 0
                for choice in getattr(chunk, "choices", None) or []:
                    delta = getattr(choice, "delta", None)
                    if delta is None:
                        continue
                    if getattr(delta, "content", None):
                        text_parts.append(delta.content)
                        result["answer"] += delta.content
                        yield {"type": "text", "text": delta.content}
                    for tc in getattr(delta, "tool_calls", None) or []:
                        idx = getattr(tc, "index", 0) or 0
                        slot = tool_calls.setdefault(
                            idx,
                            {
                                "id": "",
                                "type": "function",
                                "function": {"name": "", "arguments": ""},
                            },
                        )
                        if getattr(tc, "id", None):
                            slot["id"] = tc.id
                        fn = getattr(tc, "function", None)
                        if fn is not None:
                            if getattr(fn, "name", None):
                                slot["function"]["name"] = fn.name
                            if getattr(fn, "arguments", None):
                                slot["function"]["arguments"] += fn.arguments
            for key, value in usage.items():
                result["usage"][key] += value

            if not tool_calls:
                return

            result["used_tool"] = True
            ordered_calls = [tool_calls[i] for i in sorted(tool_calls)]
            for tc in ordered_calls:
                name = tc["function"]["name"]
                result["tools_used"].append(name)
                yield {"type": "tool", "name": name}

            messages.append(
                {
                    "role": "assistant",
                    "content": "".join(text_parts) or None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {
                                "name": tc["function"]["name"],
                                "arguments": tc["function"]["arguments"],
                            },
                        }
                        for tc in ordered_calls
                    ],
                }
            )
            for tc in ordered_calls:
                name = tc["function"]["name"]
                tool_result = execute_tool(name, tc["function"]["arguments"])
                messages.append(
                    {"role": "tool", "tool_call_id": tc["id"], "content": tool_result}
                )

        result["answer"] = "抱歉，处理超时了。"
        yield {"type": "text", "text": result["answer"]}

    def _call_llm_with_tools(self, messages: list[dict]) -> tuple[str, bool, list[str], dict]:
        """function calling 循环：模型可多次调工具，直到给出最终答案。返回 (答案, 是否调工具, 工具名列表, usage 汇总)"""
        used_tool = False
        tools_used: list[str] = []
        usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        for _ in range(5):
            resp = self._call_llm_once(messages)
            u = getattr(resp, "usage", None)
            if u is not None:
                usage["prompt_tokens"] += getattr(u, "prompt_tokens", 0) or 0
                usage["completion_tokens"] += getattr(u, "completion_tokens", 0) or 0
                usage["total_tokens"] += getattr(u, "total_tokens", 0) or 0
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return msg.content or "", used_tool, tools_used, usage
            used_tool = True
            # 回传 assistant 的 tool_calls
            messages.append(
                {
                    "role": "assistant",
                    "content": msg.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments or "",
                            },
                        }
                        for tc in msg.tool_calls
                    ],
                }
            )
            for tc in msg.tool_calls:
                name = tc.function.name
                tools_used.append(name)
                result = execute_tool(name, tc.function.arguments or "")
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
        return "抱歉，处理超时了。", used_tool, tools_used, usage
