"""问答核心测试：用 Fake LLM，不依赖真实 API"""
import types

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


class _StreamDelta:
    def __init__(self, content: str) -> None:
        self.content = content
        self.tool_calls = None


class _StreamChoice:
    def __init__(self, content: str) -> None:
        self.delta = _StreamDelta(content)


class _StreamChunk:
    def __init__(self, content: str) -> None:
        self.choices = [_StreamChoice(content)]
        self.usage = None


class _StreamResp:
    def __init__(self, content: str) -> None:
        self._chunks = [_StreamChunk(content)]

    def __iter__(self):
        return iter(self._chunks)


class _StreamFakeClient:
    def __init__(self, content: str = "员工每年 10 天带薪年假 [1]。") -> None:
        self._content = content

    @property
    def chat(self):
        return self

    @property
    def completions(self):
        return self

    def create(self, **kwargs):
        assert kwargs.get("stream") is True, "流式接口必须传 stream=True"
        return _StreamResp(self._content)


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


def test_answer_stream_yields_tokens():
    """流式问答：逐段产出内容，结束后返回引用等元数据"""
    _prepare_doc()
    from app.agent.qa import QaEngine
    from app.config import settings
    from app.knowledge.indexer import VectorIndex
    from app.session.store import SessionStore

    fake = _StreamFakeClient()
    engine = QaEngine(
        VectorIndex(f"{settings.data_dir}/chroma"),
        SessionStore(f"{settings.data_dir}/sessions.db"),
        client=fake,
    )
    events = list(engine.answer_stream("u1", "stream-s1", "员工每年几天年假？"))
    texts = [e["text"] for e in events if e["type"] == "text"]
    assert "".join(texts) == "员工每年 10 天带薪年假 [1]。"
    assert events[-1]["type"] == "done"
    assert events[-1]["data"]["references"]
    assert events[-1]["data"]["answer"] == "员工每年 10 天带薪年假 [1]。"


class _FakeStreamEngine:
    def answer_stream(self, user_id: str, session_id: str, question: str):
        yield {"type": "tool", "name": "current_time"}
        yield {"type": "text", "text": "现在是 2026-08-12。"}
        yield {
            "type": "done",
            "data": {
                "answer": "现在是 2026-08-12。",
                "references": [],
                "refused": False,
                "used_tool": True,
                "tools_used": ["current_time"],
                "usage": {},
                "cost": 0,
                "provider": "deepseek",
                "session_id": session_id,
            },
        }


def test_chat_stream_sse(monkeypatch):
    """SSE 接口返回 token / done 事件"""
    import app.agent.router as router_mod

    monkeypatch.setattr(router_mod, "_engine", _FakeStreamEngine())
    r = client.post(
        "/api/chat/stream",
        json={"user_id": "u1", "session_id": "s1", "message": "现在几点？"},
    )
    assert r.status_code == 200
    assert "event: tool" in r.text
    assert "event: token" in r.text
    assert "event: done" in r.text
    assert "现在是 2026-08-12。" in r.text


def test_llm_retry_then_success():
    """LLM 调用失败时按配置重试，成功一次后返回"""
    import httpx
    from openai import APIConnectionError

    from app.agent.qa import QaEngine
    from app.config import settings
    from app.knowledge.indexer import VectorIndex
    from app.session.store import SessionStore

    class _RetryClient:
        def __init__(self) -> None:
            self.calls = 0

        @property
        def chat(self):
            return self

        @property
        def completions(self):
            return self

        def create(self, **kwargs):
            self.calls += 1
            if self.calls <= 2:
                raise APIConnectionError(
                    message="boom",
                    request=httpx.Request("POST", "http://example.com"),
                )
            return _FakeResp("调用成功")

    fake = _RetryClient()
    engine = QaEngine(
        VectorIndex(f"{settings.data_dir}/chroma"),
        SessionStore(f"{settings.data_dir}/sessions.db"),
        client=fake,
    )
    engine._ensure_client()
    resp = engine._call_llm_once([])
    assert fake.calls == 3
    assert resp.choices[0].message.content == "调用成功"


def test_chat_degraded_when_llm_unavailable(monkeypatch):
    """模型服务不可用时不返回 500，而是降级为友好提示"""
    import app.agent.router as router_mod
    from app.agent.qa import LLMUnavailableError

    class _FailEngine:
        def answer(self, user_id: str, session_id: str, question: str, manual_hits=None):
            raise LLMUnavailableError("模型服务挂了")

    monkeypatch.setattr(router_mod, "_engine", _FailEngine())
    r = client.post(
        "/api/chat",
        json={"user_id": "u1", "session_id": "s1", "message": "现在几点？"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["degraded"] is True
    assert "暂时不可用" in body["answer"]


class _ToolFakeChoice:
    def __init__(self, msg) -> None:
        self.message = msg


class _ToolFakeResp:
    def __init__(self, msg) -> None:
        self.choices = [_ToolFakeChoice(msg)]


def _tool_call_msg(tool_name: str, arguments: str) -> object:
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
            return _ToolFakeResp(_tool_call_msg("query_employee", '{"employee_id": "001"}'))
        return _ToolFakeResp(
            types.SimpleNamespace(content="张伟在技术部担任后端工程师 [1]。", tool_calls=None)
        )


def test_tool_call_flow():
    """模型调工具 → 执行结果回传 → 基于工具数据回答"""
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

    last_turn = SessionStore(f"{settings.data_dir}/sessions.db").list_turns()[-1]
    assert last_turn["tools_used"] == ["query_employee"], "日志应记录具体工具名"


def test_mock_api_http():
    """mock 内部 API 可通过 HTTP 访问（笔试验收用）"""
    r = client.get("/api/employee/001")
    assert r.status_code == 200
    assert r.json()["department"] == "技术部"
    assert client.get("/api/employee/999").status_code == 404
    assert client.get("/api/attendance/001").status_code == 200
    assert client.get("/api/orders/004").status_code == 200
