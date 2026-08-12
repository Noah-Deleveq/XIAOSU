"""飞书长连接消息解析与问答处理测试"""
from lark_oapi.api.im.v1 import P2ImMessageReceiveV1

from app.im import feishu_bot


def test_extract_text():
    """从飞书事件里提取用户、会话、文本内容和消息 ID"""
    data = P2ImMessageReceiveV1(
        {
            "event": {
                "sender": {"sender_id": {"open_id": "ou_xiaosu"}},
                "message": {
                    "message_id": "om_xiaosu",
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
        "om_xiaosu",
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

    def answer_stream(self, user_id: str, session_id: str, question: str, manual_hits=None):
        yield {"type": "text", "text": "根据《员工手册》，员工每年 10 天带薪年假 [1]。"}
        yield {
            "type": "done",
            "data": self.answer(user_id, session_id, question, manual_hits),
        }


def test_handle_feishu_text(monkeypatch):
    """飞书卡片启动失败时回退普通文本回复"""
    def _fail(_chat_id: str, _content: str, _reply_to: str | None = None) -> None:
        raise RuntimeError("card unavailable")

    monkeypatch.setattr(feishu_bot, "_engine", _FeishuEngine())
    sent = []
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_text",
        lambda chat_id, content, reply_to=None: sent.append((chat_id, content)),
    )
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_card",
        _fail,
    )

    feishu_bot.handle_feishu_text("ou_xiaosu", "oc_xiaosu", "@小苏 员工每年几天年假？")

    assert sent and sent[0][0] == "oc_xiaosu"
    assert "10 天带薪年假" in sent[0][1]
    assert "员工手册.md" in sent[0][1]


def test_handle_feishu_text_streams_card(monkeypatch):
    """飞书收到文本后发送 AI 卡片并流式更新最终内容"""
    monkeypatch.setattr(feishu_bot, "_engine", _FeishuEngine())
    created = []
    patches = []
    sent = []
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_card",
        lambda chat_id, content, reply_to=None: created.append((chat_id, content))
        or "om_xiaosu",
    )
    monkeypatch.setattr(
        feishu_bot,
        "patch_feishu_card",
        lambda message_id, content: patches.append((message_id, content)),
    )
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_text",
        lambda chat_id, content, reply_to=None: sent.append((chat_id, content)),
    )

    feishu_bot.handle_feishu_text("ou_xiaosu", "oc_xiaosu", "@小苏 员工每年几天年假？")

    assert created and created[0][0] == "oc_xiaosu"
    assert "正在思考" in created[0][1]
    assert patches and patches[-1][0] == "om_xiaosu"
    assert "10 天带薪年假" in patches[-1][1]
    assert "员工手册.md" in patches[-1][1]
    assert sent == []


def test_handle_feishu_card_patch_failure_falls_back_to_text(monkeypatch):
    """飞书卡片更新失败时仍向用户发送完整文本答案"""
    def _fail(_message_id: str, _content: str) -> None:
        raise RuntimeError("patch failed")

    monkeypatch.setattr(feishu_bot, "_engine", _FeishuEngine())
    sent = []
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_card",
        lambda chat_id, content, reply_to=None: "om_xiaosu",
    )
    monkeypatch.setattr(
        feishu_bot,
        "patch_feishu_card",
        _fail,
    )
    monkeypatch.setattr(
        feishu_bot,
        "send_feishu_text",
        lambda chat_id, content, reply_to=None: sent.append((chat_id, content)),
    )

    feishu_bot.handle_feishu_text("ou_xiaosu", "oc_xiaosu", "@小苏 员工每年几天年假？")

    assert len(sent) == 1
    assert sent[0][0] == "oc_xiaosu"
    assert "10 天带薪年假" in sent[0][1]
    assert "员工手册.md" in sent[0][1]


def test_send_feishu_text_uses_api(monkeypatch):
    """主动回复走飞书 im.v1.message.create 接口"""

    class _Resp:
        code = 0
        data = type("Data", (), {"message_id": "om_reply"})()

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


def test_send_feishu_text_replies_to_message(monkeypatch):
    """收到用户消息后优先回复原消息，而不是另发一条新消息"""

    class _Resp:
        code = 0
        data = type("Data", (), {"message_id": "om_reply"})()

    class _Message:
        def reply(self, request):
            assert request.message_id == "om_source"
            assert request.body.msg_type == "text"
            return _Resp()

        def create(self, request):
            raise AssertionError("reply_to 生效时不应再调用 create")

    class _Im:
        def __init__(self) -> None:
            self.v1 = type("V1", (), {"message": _Message()})()

    class _Client:
        def __init__(self) -> None:
            self.im = _Im()

    monkeypatch.setattr(feishu_bot, "get_api_client", lambda: _Client())
    feishu_bot.send_feishu_text("oc_xiaosu", "你好", "om_source")


def test_send_feishu_card_uses_api(monkeypatch):
    """飞书 AI 卡片走 im.v1.message.create 接口并返回消息 ID"""

    class _Resp:
        code = 0
        data = type("Data", (), {"message_id": "om_card"})()

    class _Message:
        def create(self, request):
            assert request.receive_id_type == "chat_id"
            assert request.body.msg_type == "interactive"
            return _Resp()

    class _Im:
        def __init__(self) -> None:
            self.v1 = type("V1", (), {"message": _Message()})()

    class _Client:
        def __init__(self) -> None:
            self.im = _Im()

    monkeypatch.setattr(feishu_bot, "get_api_client", lambda: _Client())
    assert feishu_bot.send_feishu_card("oc_xiaosu", "{}") == "om_card"


def test_patch_feishu_card_uses_api(monkeypatch):
    """飞书流式更新走 im.v1.message.patch 接口"""

    class _Resp:
        code = 0

    class _Message:
        def patch(self, request):
            assert request.message_id == "om_card"
            assert "生成完成" in request.body.content
            return _Resp()

    class _Im:
        def __init__(self) -> None:
            self.v1 = type("V1", (), {"message": _Message()})()

    class _Client:
        def __init__(self) -> None:
            self.im = _Im()

    monkeypatch.setattr(feishu_bot, "get_api_client", lambda: _Client())
    feishu_bot.patch_feishu_card("om_card", '{"text":"生成完成"}')
