"""文件上传问答与可观测性测试"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


class _FileEngine:
    def __init__(self) -> None:
        self.manual_hits: list[dict] | None = None

    @property
    def model(self) -> str:
        return "fake-model"

    def answer(
        self,
        user_id: str,
        session_id: str,
        question: str,
        manual_hits: list[dict] | None = None,
    ) -> dict:
        self.manual_hits = manual_hits
        return {
            "answer": "根据文件，员工每年 10 天带薪年假 [1]。",
            "references": manual_hits or [],
            "refused": False,
            "used_tool": False,
            "tools_used": [],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
            "cost": 0.0001,
            "provider": "deepseek",
            "session_id": session_id,
        }

    def answer_stream(
        self,
        user_id: str,
        session_id: str,
        question: str,
        manual_hits: list[dict] | None = None,
    ):
        self.manual_hits = manual_hits
        yield {"type": "text", "text": "根据文件，员工每年 10 天带薪年假 [1]。"}
        yield {
            "type": "done",
            "data": {
                "answer": "根据文件，员工每年 10 天带薪年假 [1]。",
                "references": manual_hits or [],
                "refused": False,
                "used_tool": False,
                "tools_used": [],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 5,
                    "total_tokens": 15,
                },
                "cost": 0.0001,
                "provider": "deepseek",
                "session_id": session_id,
            },
        }


def test_chat_file_endpoint(monkeypatch):
    """上传文件后问答：问题命中上传文件内容，引用来源是文件名"""
    import app.agent.router as router_mod

    engine = _FileEngine()
    monkeypatch.setattr(router_mod, "_engine", engine)
    r = client.post(
        "/api/chat/file",
        data={"question": "年假几天？"},
        files={"file": ("假期.txt", "员工每年 10 天带薪年假。".encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200
    assert engine.manual_hits and engine.manual_hits[0]["name"] == "假期.txt"
    assert "10 天" in r.json()["answer"]


def test_chat_file_stream_sse(monkeypatch):
    """文件上传问答也支持流式输出"""
    import app.agent.router as router_mod

    engine = _FileEngine()
    monkeypatch.setattr(router_mod, "_engine", engine)
    r = client.post(
        "/api/chat/file/stream",
        data={"question": "年假几天？"},
        files={"file": ("假期.txt", "员工每年 10 天带薪年假。".encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200
    assert "event: token" in r.text
    assert "event: done" in r.text
    assert "10 天" in r.text


def test_trace_store_and_api():
    """请求链路记录可写入并通过 /api/traces 读取"""
    from app.state import traces

    traces.add(
        "test",
        user_id="u1",
        session_id="s1",
        provider="deepseek",
        model="fake-model",
        duration_ms=12,
        usage={"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        cost=0.0001,
        tools_used=["current_time"],
    )
    rows = traces.list()
    assert rows[0]["request_type"] == "test"
    assert rows[0]["tools_used"] == ["current_time"]

    r = client.get("/api/traces")
    assert r.status_code == 200
    assert any(t["request_type"] == "test" for t in r.json()["traces"])
