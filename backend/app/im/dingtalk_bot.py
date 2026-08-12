"""钉钉 Stream 模式机器人：收 @消息 → 问答（RAG/工具）→ 回复群/单聊"""
import logging
import re

import websockets.exceptions  # noqa: F401  兼容 websockets 17
import dingtalk_stream
from dingtalk_stream import AckMessage, ChatbotHandler, ChatbotMessage

from app.agent.qa import QaEngine
from app.state import index, sessions

logger = logging.getLogger("xiaosu.im")

_engine = QaEngine(index, sessions)


def clean_mention(text: str) -> str:
    """去掉消息开头的 @小苏 及空白，取出真正的问题"""
    cleaned = re.sub(r"@[\w\u4e00-\u9fa5]+\s*", "", text, count=1)
    return cleaned.strip()


def build_reply(result: dict) -> str:
    """组装回复文本：答案 + 引用来源"""
    reply = result["answer"]
    refs = [r["name"] for r in result["references"]]
    if refs:
        sources = "、".join(dict.fromkeys(refs))
        reply += f"\n\n📎 来源：{sources}"
    return reply


class XiaoSuBot(ChatbotHandler):
    async def process(self, callback: dingtalk_stream.CallbackMessage):
        msg = ChatbotMessage.from_dict(callback.data)
        text = getattr(msg.text, "content", "") or ""
        question = clean_mention(text)
        if not question:
            return AckMessage.STATUS_OK, "EMPTY"

        user_id = msg.sender_staff_id or "unknown"
        session_id = msg.conversation_id or user_id

        try:
            result = _engine.answer(user_id, session_id, question)
            reply = build_reply(result)
            self.reply_text(reply, msg)
            logger.info("回答 %s: %s -> %s", user_id, question[:30], reply[:60])
        except Exception as e:  # noqa: BLE001
            logger.exception("处理消息失败")
            try:
                self.reply_text(f"抱歉，处理你的问题出错了：{e}", msg)
            except Exception:  # noqa: BLE001
                pass
        return AckMessage.STATUS_OK, "OK"


def build_stream_client() -> dingtalk_stream.DingTalkStreamClient:
    """创建并配置钉钉 Stream 客户端。

    关键：必须用 ChatbotMessage.TOPIC（/v1.0/im/bot/messages/get）注册，
    钉钉推送的 chatbot 消息 headers.topic 就是它；注册其他字符串会导致消息全部被丢弃。
    """
    from app.config import settings

    credential = dingtalk_stream.Credential(
        settings.dingtalk_app_key, settings.dingtalk_app_secret
    )
    client = dingtalk_stream.DingTalkStreamClient(credential)
    client.register_callback_handler(ChatbotMessage.TOPIC, XiaoSuBot())
    return client


def start_dingtalk_bot() -> None:
    """启动钉钉 Stream 长连接（阻塞，放独立线程运行）"""
    from app.config import settings

    if not settings.dingtalk_app_key or not settings.dingtalk_app_secret:
        logger.warning("未配置 DINGTALK_APP_KEY/SECRET，跳过钉钉连接")
        return
    client = build_stream_client()
    logger.info("钉钉 Stream 机器人启动中...")
    client.start_forever()
