"""问答核心测试：用 Fake LLM，不依赖真实 API"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = type("M", (), {"content": content, "tool_calls": None})()


class _FakeResp:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class _FakeClient:
    """Fake OpenAI client：记录 messages，返回可配置的固定答案"""

    def __init__(self, content: str = "根据《员工手册》，员工每年享有 10 天带薪年假 [1]。") -> None:
        self.last_messages: list[dict] = []
        self._content = content

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.last_messages = kwargs.get("messages", [])
        return _FakeResp(self._content)


def _prepare_doc() -> None:
    r = client.post(
        "/api/docs",
        files={"file": ("员工手册.txt", "员工手册\n\n年假\n\n员工每年享有 10 天带薪年假，入职满一年后即可申请。".encode(), "text/plain")},
    )
    assert r.status_code == 200


def test_chat_answer_with_reference():
    """有检索结果 → 返回答案 + 引用 + 不拒答"""
    _prepare_doc()
    from app.agent.qa import QaEngine
    from app.config import settings
    from app.knowledge.indexer import VectorIndex
    from app.session.store import SessionStore

    fake = _FakeClient()
    engine = QaEngine(
        VectorIndex(f"{settings.data_dir}/chroma"),
        SessionStore(f"{settings.data_dir}/sessions.db"),
        client=fake,
    )
    result = engine.answer("u1", "s1", "员工每年几天年假？")
    assert result["refused"] is False
    assert result["references"], "应有引用"
    assert "10 天" in result["references"][0]["text"]
    joined = "\n".join(m["content"] for m in fake.last_messages)
    assert "员工手册" in joined and "年假" in joined


def test_chat_refused_when_no_hit():
    """无检索结果且模型说没找到 → 拒答"""
    from app.agent.qa import QaEngine
    from app.config import settings
    from app.knowledge.indexer import VectorIndex
    from app.session.store import SessionStore

    engine = QaEngine(
        VectorIndex(f"{settings.data_dir}/chroma"),
        SessionStore(f"{settings.data_dir}/sessions.db"),
        client=_FakeClient(content="文档里没找到相关内容。"),
    )
    result = engine.answer("u1", "s2", "我们公司CEO的家庭住址是？")
    assert result["refused"] is True
    assert result["references"] == []


def test_chat_multiturn_keeps_history():
    """多轮对话：第二轮 prompt 应包含第一轮的历史"""
    _prepare_doc()
    from app.agent.qa import QaEngine
    from app.config import settings
    from app.knowledge.indexer import VectorIndex
    from app.session.store import SessionStore

    fake = _FakeClient()
    sessions = SessionStore(f"{settings.data_dir}/sessions.db")
    engine = QaEngine(VectorIndex(f"{settings.data_dir}/chroma"), sessions, client=fake)
    engine.answer("u1", "s3", "员工每年几天年假？")
    engine.answer("u1", "s3", "那报销呢？")
    history = sessions.get_messages("u1", "s3")
    assert len(history) >= 4  # 2 轮 × (user+assistant)
    assert any("年假" in m["content"] for m in history)
