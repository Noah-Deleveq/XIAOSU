"""模拟真实钉钉消息：验证 process 从收消息到回复的全链路（回归测试）"""
import asyncio
import json

import dingtalk_stream
from dingtalk_stream import CallbackMessage

from app.im import dingtalk_bot as mod
from app.im.dingtalk_bot import XiaoSuBot


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
