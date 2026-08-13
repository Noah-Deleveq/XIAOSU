"""钉钉消息处理测试：@去重、回复组装、全链路与 topic 注册"""
import asyncio
import json

import dingtalk_stream
from dingtalk_stream import CallbackMessage

from app import state
from app.im import dingtalk_bot as mod
from app.im.dingtalk_bot import XiaoSuBot, build_reply, build_stream_client, clean_mention


def test_clean_mention():
    """去掉开头的 @小苏"""
    assert clean_mention("@小苏 员工每年几天年假？") == "员工每年几天年假？"
    assert clean_mention("@小苏\n报销需要什么？") == "报销需要什么？"
    # 无 @ 时原样返回
    assert clean_mention("直接问问题") == "直接问问题"


def test_build_reply_with_references():
    """答案带引用来源"""
    result = {
        "answer": "员工每年 10 天带薪年假 [1]。",
        "references": [
            {"name": "员工手册.md", "text": "..."},
            {"name": "员工手册.md", "text": "..."},
            {"name": "FAQ.md", "text": "..."},
        ],
    }
    reply = build_reply(result)
    assert "10 天带薪年假" in reply
    assert "员工手册.md、FAQ.md" in reply  # 去重后
    assert "📎 来源" in reply


def test_build_reply_without_references():
    """无引用（如工具查询结果）时不加来源"""
    result = {"answer": "张伟在技术部。", "references": []}
    reply = build_reply(result)
    assert reply == "张伟在技术部。"


class FakeEngine:
    def answer(self, user_id: str, session_id: str, question: str) -> dict:
        return {
            "answer": "张伟在技术部担任后端工程师 [1]。",
            "references": [
                {"name": "员工手册.md", "text": "技术部", "doc_id": "d1", "chunk_index": 0}
            ],
        }


def _make_callback(content: str) -> CallbackMessage:
    return CallbackMessage.from_dict(
        {
            "specVersion": "1.0",
            "type": "callback",
            "headers": {
                "topic": "/v1.0/im/bot/messages/get",
                "eventId": "event1",
                "eventBornTime": 1710000000000,
                "messageId": "msg1",
            },
            "data": json.dumps(
                {
                    "msgtype": "text",
                    "text": {"content": content},
                    "senderStaffId": "u001",
                    "conversationId": "cid001",
                    "conversationType": "1",
                    "sessionWebhook": "https://oapi.dingtalk.com/robot/send?access_token=fake",
                    "msgId": "msg1",
                    "atUsers": [],
                }
            ),
        }
    )


def _make_bot_with_replies():
    bot = XiaoSuBot()
    replies = []

    def fake_reply(text: str, incoming_message) -> None:
        replies.append(text)

    bot.reply_text = fake_reply
    return bot, replies


def test_process_replies_with_engine():
    """收到 @消息 → 调 engine → 回复（含引用来源）"""
    mod._engine = FakeEngine()
    bot, replies = _make_bot_with_replies()
    code, msg = asyncio.run(bot.process(_make_callback("@小苏 员工001是哪个部门的？")))
    assert replies, "应调用回复（回归：曾因 msg.chatbot 不存在而不回复）"
    assert "张伟" in replies[0]
    assert "员工手册.md" in replies[0]
    assert code == dingtalk_stream.AckMessage.STATUS_OK


def test_process_empty_message_no_reply():
    """只有 @ 没有内容的消息不应回复"""
    mod._engine = FakeEngine()
    bot, replies = _make_bot_with_replies()
    asyncio.run(bot.process(_make_callback("@小苏  ")))
    assert replies == []


class FakeCard:
    def __init__(self) -> None:
        self.card_instance_id = "card-1"
        self.texts: list[str] = []
        self.finished: str | None = None
        self.failed = False

    def ai_streaming(self, markdown: str, append: bool = False) -> None:
        self.texts.append(markdown)

    def ai_finish(self, markdown: str | None = None, button_list: list | None = None, tips: str = "") -> None:
        self.finished = markdown

    def ai_fail(self) -> None:
        self.failed = True


class StreamEngine:
    @property
    def model(self) -> str:
        return "fake-model"

    def answer_stream(self, user_id: str, session_id: str, question: str, manual_hits=None):
        yield {"type": "tool", "name": "current_time"}
        yield {"type": "text", "text": "现在"}
        yield {"type": "text", "text": "是 10 点"}
        yield {
            "type": "done",
            "data": {
                "answer": "现在是 10 点",
                "references": [{"name": "员工手册.md", "text": "..."}],
                "refused": False,
                "used_tool": True,
                "tools_used": ["current_time"],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
                "cost": 0.0001,
                "provider": "deepseek",
                "session_id": session_id,
            },
        }


def test_process_streams_with_ai_card(monkeypatch):
    """钉钉回复走 AI 卡片流式输出，最终展示引用来源"""
    bot, _ = _make_bot_with_replies()
    card = FakeCard()
    bot.dingtalk_client = object()
    bot.ai_markdown_card_start = lambda msg, title="": card
    mod._engine = StreamEngine()

    asyncio.run(bot.process(_make_callback("@小苏 现在几点？")))

    assert "".join(card.texts) == "现在是 10 点"
    assert "员工手册.md" in card.finished
    assert card.failed is False


def test_stream_client_registers_correct_topic():
    """注册的 topic 必须是钉钉 chatbot 消息的 TOPIC"""
    client = build_stream_client()
    assert list(client.callback_handler_map.keys()) == [
        dingtalk_stream.ChatbotMessage.TOPIC
    ]


def test_process_ignores_disabled_channel(monkeypatch):
    """运行期关闭钉钉机器人后，消息直接确认但不回复"""
    bot, replies = _make_bot_with_replies()
    monkeypatch.setitem(state.im_enabled, "dingtalk", False)
    try:
        code, status = asyncio.run(bot.process(_make_callback("@小苏 现在几点？")))
        assert replies == []
        assert code == dingtalk_stream.AckMessage.STATUS_OK
        assert status == "DISABLED"
    finally:
        monkeypatch.setitem(state.im_enabled, "dingtalk", True)
