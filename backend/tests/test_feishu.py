"""飞书长连接消息解析与文本回复测试"""
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from app import state
from app.agent.qa import LLMUnavailableError
from app.im import feishu_bot


def test_extract_text():
    """从飞书事件里提取用户、会话和文本内容"""
    data = P2ImMessageReceiveV1(
        {
            "event": {
                "sender": {"sender_id": {"open_id": "ou_xiaosu"}},
                "message": {
                    "message_type": "text",
                    "content": '{"text":"@小苏 员工每年几天年假？"}',
                    "chat_id": "oc_xiaosu",
                },
            }
        }
    )
    assert feishu_bot.extract_text(data) == (
        "ou_xiaosu",
        "oc_xiaosu",
        "@小苏 员工每年几天年假？",
    )


class _FeishuEngine:
    @property
    def model(self) -> str:
        return "fake-model"

    def answer(self, user_id: str, session_id: str, question: str, manual_hits=None):
        return {
            "answer": "根据《员工手册》，员工每年 10 天带薪年假 [1]。",
            "references": [{"name": "员工手册.md", "text": "员工每年 10 天带薪年假"}],
            "refused": False,
            "used_tool": False,
            "tools_used": [],
            "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
            "cost": 0.0001,
            "provider": "deepseek",
            "session_id": session_id,
        }


def test_handle_feishu_text(monkeypatch):
    """飞书收到文本后调用问答引擎并发送文本回复"""
    monkeypatch.setattr(feishu_bot, "_engine", _FeishuEngine())
    sent = []
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_text",
        lambda chat_id, content: sent.append((chat_id, content)),
    )

    feishu_bot.handle_feishu_text("ou_xiaosu", "oc_xiaosu", "@小苏 员工每年几天年假？")

    assert sent and sent[0][0] == "oc_xiaosu"
    assert "10 天带薪年假" in sent[0][1]
    assert "员工手册.md" in sent[0][1]


def test_handle_feishu_text_error_fallback(monkeypatch):
    """飞书处理失败时回复友好错误文本"""

    class _FailEngine:
        def answer(self, user_id: str, session_id: str, question: str, manual_hits=None):
            raise RuntimeError("boom")

    monkeypatch.setattr(feishu_bot, "_engine", _FailEngine())
    sent = []
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_text",
        lambda chat_id, content: sent.append((chat_id, content)),
    )

    feishu_bot.handle_feishu_text("ou_xiaosu", "oc_xiaosu", "@小苏 员工每年几天年假？")

    assert sent and "抱歉" in sent[0][1]


def test_handle_feishu_text_retries_llm_once(monkeypatch):
    """首次模型连接失败时自动重试一次，避免冷启动直接报错"""

    class _RetryEngine:
        def __init__(self) -> None:
            self.calls = 0

        def answer(self, user_id: str, session_id: str, question: str, manual_hits=None):
            self.calls += 1
            if self.calls == 1:
                raise LLMUnavailableError("cold start")
            return {
                "answer": "根据《员工手册》，员工每年 10 天带薪年假 [1]。",
                "references": [{"name": "员工手册.md", "text": "员工每年 10 天带薪年假"}],
                "refused": False,
                "used_tool": False,
                "tools_used": [],
                "usage": {},
                "cost": 0,
                "provider": "deepseek",
                "session_id": session_id,
            }

    engine = _RetryEngine()
    monkeypatch.setattr(feishu_bot, "_engine", engine)
    sent = []
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_text",
        lambda chat_id, content: sent.append((chat_id, content)),
    )

    feishu_bot.handle_feishu_text("ou_xiaosu", "oc_xiaosu", "@小苏 员工每年几天年假？")

    assert engine.calls == 2
    assert sent and "10 天带薪年假" in sent[0][1]


def test_send_feishu_text_uses_api(monkeypatch):
    """主动回复走飞书 im.v1.message.create 接口"""

    class _Resp:
        code = 0

    class _Message:
        def create(self, request):
            assert request.receive_id_type == "chat_id"
            return _Resp()

    class _Im:
        def __init__(self) -> None:
            self.v1 = type("V1", (), {"message": _Message()})()

    class _Client:
        def __init__(self) -> None:
            self.im = _Im()

    monkeypatch.setattr(feishu_bot, "get_api_client", lambda: _Client())
    feishu_bot.send_feishu_text("oc_xiaosu", "你好")


def test_on_message_ignores_duplicate_event(monkeypatch):
    """同一个 message_id 重复推送时只处理一次，避免飞书回复两条"""
    data = P2ImMessageReceiveV1(
        {
            "event": {
                "sender": {"sender_id": {"open_id": "ou_xiaosu"}},
                "message": {
                    "message_id": "om_duplicate",
                    "message_type": "text",
                    "content": '{"text":"员工 001 是哪个部门的"}',
                    "chat_id": "oc_xiaosu",
                },
            }
        }
    )
    calls = []
    monkeypatch.setattr(
        feishu_bot,
        "handle_feishu_text",
        lambda *args: calls.append(args),
    )

    feishu_bot.on_message(data)
    feishu_bot.on_message(data)

    assert len(calls) == 1


def test_on_message_ignores_disabled_channel(monkeypatch):
    """运行期关闭飞书机器人后，事件直接忽略，不回复"""
    data = P2ImMessageReceiveV1(
        {
            "event": {
                "sender": {"sender_id": {"open_id": "ou_xiaosu"}},
                "message": {
                    "message_id": "om_disabled",
                    "message_type": "text",
                    "content": '{"text":"员工 001 是哪个部门的"}',
                    "chat_id": "oc_xiaosu",
                },
            }
        }
    )
    calls = []
    monkeypatch.setattr(
        feishu_bot,
        "handle_feishu_text",
        lambda *args: calls.append(args),
    )
    monkeypatch.setitem(state.im_enabled, "feishu", False)
    try:
        feishu_bot.on_message(data)
        assert calls == []
    finally:
        monkeypatch.setitem(state.im_enabled, "feishu", True)


def test_handle_feishu_text_llm_unavailable_friendly(monkeypatch):
    from app.agent.qa import LLMUnavailableError

    class _FailEngine:
        def answer(self, user_id, session_id, question, manual_hits=None):
            raise LLMUnavailableError("boom")

    monkeypatch.setattr(feishu_bot, "_engine", _FailEngine())
    sent = []
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_text",
        lambda chat_id, content: sent.append((chat_id, content)),
    )

    feishu_bot.handle_feishu_text("ou_xiaosu", "oc_xiaosu", "@\u5c0f\u82cf hello")

    assert sent and "\u6a21\u578b\u670d\u52a1" in sent[0][1]
    assert "boom" not in sent[0][1]


def test_on_message_ignores_duplicate_event_id(monkeypatch):
    """同一个 event_id 重复推送时只处理一次。"""
    data = P2ImMessageReceiveV1(
        {
            "schema": "2.0",
            "header": {"event_id": "evt_duplicate_001", "event_type": "im.message.receive_v1"},
            "event": {
                "sender": {"sender_id": {"open_id": "ou_xiaosu"}},
                "message": {
                    "message_id": "om_event_id_case",
                    "message_type": "text",
                    "content": '{"text":"员工 2024 年假多少天？"}',
                    "chat_id": "oc_xiaosu",
                },
            },
        }
    )
    calls = []
    monkeypatch.setattr(
        feishu_bot,
        "handle_feishu_text",
        lambda *args: calls.append(args),
    )

    feishu_bot.on_message(data)
    feishu_bot.on_message(data)

    assert len(calls) == 1


def test_on_message_ignores_recent_same_question(monkeypatch):
    """同一用户短时间内发完全相同的问题，只回复一次。"""

    def make_data(message_id, event_id):
        return P2ImMessageReceiveV1(
            {
                "schema": "2.0",
                "header": {"event_id": event_id, "event_type": "im.message.receive_v1"},
                "event": {
                    "sender": {"sender_id": {"open_id": "ou_xiaosu"}},
                    "message": {
                        "message_id": message_id,
                        "message_type": "text",
                        "content": '{"text":"重复测试问题专用 001"}',
                        "chat_id": "oc_xiaosu",
                    },
                },
            }
        )

    calls = []
    monkeypatch.setattr(
        feishu_bot,
        "handle_feishu_text",
        lambda *args: calls.append(args),
    )

    feishu_bot.on_message(make_data("om_recent_1", "evt_recent_1"))
    feishu_bot.on_message(make_data("om_recent_2", "evt_recent_2"))

    assert len(calls) == 1
