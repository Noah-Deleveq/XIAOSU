"""问答核心：检索知识库 → LLM（支持 function calling 工具调用）→ 答案 + 引用 + 拒答 + 多轮"""
from openai import OpenAI

from app.config import settings
from app.knowledge.indexer import VectorIndex
from app.session.store import SessionStore
from app.tools.registry import TOOLS, execute_tool

SYSTEM_PROMPT = """你是公司内部 AI 助手「小苏」，负责根据公司文档与内部系统回答员工问题。

规则：
1. 只能依据用户提供的【参考文档】回答；答案里必须用 [1][2] 标注引用来源编号。
2. 若【参考文档】中找不到答案，明确回答「文档里没找到相关内容」，绝不编造。
3. 需要查询员工信息、考勤、销售订单或当前时间时，必须调用提供的工具获取真实数据，禁止编造。
4. 回答用中文，简洁、专业、口语友好；先给结论，再给依据。"""


class QaEngine:
    def __init__(self, index: VectorIndex, sessions: SessionStore, client: OpenAI | None = None) -> None:
        self._index = index
        self._sessions = sessions
        self._client = client or OpenAI(
            api_key=settings.llm_api_key or "sk-none",
            base_url=settings.llm_base_url,
        )
        self._model = settings.llm_model

    def answer(self, user_id: str, session_id: str, question: str) -> dict:
        hits = self._index.search(question, k=4)
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

        answer, used_tool = self._call_llm_with_tools(messages)
        self._sessions.append(user_id, session_id, question, answer)

        # 拒答判定：没调工具且模型明确说没找到
        refused = (not used_tool) and any(
            k in answer for k in ("文档里没找到", "没有找到", "无法回答")
        )
        return {
            "answer": answer,
            "references": references,
            "refused": refused,
            "session_id": session_id,
        }

    def _call_llm_with_tools(self, messages: list[dict]) -> tuple[str, bool]:
        """function calling 循环：模型可多次调工具，直到给出最终答案"""
        used_tool = False
        for _ in range(5):
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                tools=TOOLS,
                temperature=0.3,
                max_tokens=800,
            )
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return msg.content or "", used_tool
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
                result = execute_tool(tc.function.name, tc.function.arguments or "")
                messages.append(
                    {"role": "tool", "tool_call_id": tc.id, "content": result}
                )
        return "抱歉，处理超时了。", used_tool
