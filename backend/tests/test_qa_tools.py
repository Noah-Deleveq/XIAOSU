"""工具调用测试：验证 function calling 消息流（Fake LLM 模拟模型调工具）"""
import json
import types

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FakeChoice:
    def __init__(self, msg) -> None:
        self.message = msg


class _FakeResp:
    def __init__(self, msg) -> None:
        self.choices = [_FakeChoice(msg)]


def _tool_call_msg(tool_name: str, arguments: str) -> object:
    import types

    tc = types.SimpleNamespace(
        id="call_1",
        function=types.SimpleNamespace(name=tool_name, arguments=arguments),
    )
    return types.SimpleNamespace(content=None, tool_calls=[tc])


class _ToolFakeClient:
    """第一次返回 tool_call（query_employee），第二次返回最终答案"""

    def __init__(self) -> None:
        self.calls = 0
        self.messages_sent: list[dict] = []

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        self.calls += 1
        self.messages_sent = kwargs.get("messages", [])
        if self.calls == 1:
            return _FakeResp(_tool_call_msg("query_employee", '{"employee_id": "001"}'))
        return _FakeResp(types.SimpleNamespace(content="张伟在技术部担任后端工程师 [1]。", tool_calls=None))


def test_tool_call_flow():
    """模型调工具 → 执行结果回传 → 基于工具数据回答"""
    import types

    from app.agent.qa import QaEngine
    from app.config import settings
    from app.knowledge.indexer import VectorIndex
    from app.session.store import SessionStore

    fake = _ToolFakeClient()
    engine = QaEngine(
        VectorIndex(f"{settings.data_dir}/chroma"),
        SessionStore(f"{settings.data_dir}/sessions.db"),
        client=fake,
    )
    result = engine.answer("u1", "s9", "员工 001 是哪个部门的？")

    assert fake.calls == 2, "应经历 工具调用 → 最终回答 两次 LLM 调用"
    assert "张伟" in result["answer"]
    assert result["refused"] is False
    # 第二次请求的 messages 里应包含工具执行结果
    tool_msgs = [m for m in fake.messages_sent if m.get("role") == "tool"]
    assert tool_msgs, "缺少 tool 结果消息"
    assert "技术部" in tool_msgs[0]["content"]


def test_mock_api_http():
    """mock 内部 API 可通过 HTTP 访问（笔试验收用）"""
    r = client.get("/api/employee/001")
    assert r.status_code == 200
    assert r.json()["department"] == "技术部"
    assert client.get("/api/employee/999").status_code == 404
    assert client.get("/api/attendance/001").status_code == 200
    assert client.get("/api/orders/004").status_code == 200
