"""问答核心：检索知识库 → 组装 prompt → LLM → 答案 + 引用 + 拒答 + 多轮"""
from openai import OpenAI

from app.config import settings
from app.knowledge.indexer import VectorIndex
from app.session.store import SessionStore

SYSTEM_PROMPT = """你是公司内部 AI 助手「小苏」，负责根据公司文档回答员工问题。

规则：
1. 只能依据用户提供的【参考文档】回答；答案里必须用 [1][2] 标注引用来源编号。
2. 若【参考文档】中找不到答案，明确回答「文档里没找到相关内容」，绝不编造。
3. 回答用中文，简洁、专业、口语友好；先给结论，再给依据。"""


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
        """回答一个问题，返回答案 + 引用 + 是否拒答"""
        hits = self._index.search(question, k=4)

        # 拒答机制：检索不到相关内容，直接拒答，绝不瞎编
        if not hits:
            answer = "文档里没找到相关内容，我无法回答这个问题。"
            self._sessions.append(user_id, session_id, question, answer)
            return {"answer": answer, "references": [], "refused": True, "session_id": session_id}

        references = [
            {"name": h["name"], "text": h["text"][:300], "doc_id": h["doc_id"], "chunk_index": h["chunk_index"]}
            for h in hits
        ]
        context = "\n\n".join(
            f"[{i + 1}] 来源《{h['name']}》第 {h['chunk_index'] + 1} 段：\n{h['text']}"
            for i, h in enumerate(hits)
        )

        messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]
        # 多轮对话：带上历史（按 user+session 隔离）
        messages += self._sessions.get_messages(user_id, session_id)
        messages.append(
            {
                "role": "user",
                "content": f"【参考文档】\n{context}\n\n【问题】{question}",
            }
        )

        answer = self._call_llm(messages)
        self._sessions.append(user_id, session_id, question, answer)
        return {
            "answer": answer,
            "references": references,
            "refused": ("文档里没找到" in answer) or ("没有找到" in answer),
            "session_id": session_id,
        }

    def _call_llm(self, messages: list[dict]) -> str:
        resp = self._client.chat.completions.create(
            model=self._model,
            messages=messages,
            temperature=0.3,
            max_tokens=800,
        )
        return resp.choices[0].message.content or ""
