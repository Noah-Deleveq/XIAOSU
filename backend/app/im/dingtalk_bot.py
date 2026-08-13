"""钉钉 Stream 模式机器人：收 @消息 → 问答（RAG/工具）→ 回复群/单聊"""
import asyncio
import logging
import time

import websockets.exceptions  # noqa: F401  兼容 websockets 17
import dingtalk_stream
from dingtalk_stream import AckMessage, ChatbotHandler, ChatbotMessage

from app.agent.qa import QaEngine
from app.im.common import build_reply, clean_mention
from app import state
from app.state import index, sessions, traces

logger = logging.getLogger("xiaosu.im")

_engine = QaEngine(index, sessions)


class XiaoSuBot(ChatbotHandler):
    async def process(self, callback: dingtalk_stream.CallbackMessage):
        if not state.im_enabled.get("dingtalk", True):
            return AckMessage.STATUS_OK, "DISABLED"
        msg = ChatbotMessage.from_dict(callback.data)
        text = getattr(msg.text, "content", "") or ""
        question = clean_mention(text)
        if not question:
            return AckMessage.STATUS_OK, "EMPTY"

        user_id = msg.sender_staff_id or "unknown"
        session_id = msg.conversation_id or user_id
        started = time.perf_counter()
        card = None
        completed = False

        try:
            # AI 卡片流式回复；启动失败或客户端未连接时回退普通文本
            if getattr(self, "dingtalk_client", None) is not None:
                try:
                    card = self.ai_markdown_card_start(msg, title="小苏")
                except Exception as e:  # noqa: BLE001
                    logger.warning("AI 卡片启动失败，回退文本回复: %s", e)
                    card = None
                if card is None or not getattr(card, "card_instance_id", ""):
                    card = None

            if card is None:
                result = _engine.answer(user_id, session_id, question)
                reply = build_reply(result)
                self.reply_text(reply, msg)
                traces.add(
                    "im_chat",
                    user_id,
                    session_id,
                    provider=result.get("provider", ""),
                    model=getattr(_engine, "model", ""),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    usage=result.get("usage"),
                    cost=result.get("cost", 0),
                    tools_used=result.get("tools_used"),
                )
                completed = True
                logger.info("回答 %s: %s -> %s", user_id, question[:30], reply[:60])
            else:
                done_data: dict | None = None
                for event in _engine.answer_stream(user_id, session_id, question):
                    if event["type"] == "text":
                        await asyncio.to_thread(card.ai_streaming, event["text"], True)
                    elif event["type"] == "done":
                        done_data = event["data"]
                        final_reply = build_reply(done_data)
                        await asyncio.to_thread(card.ai_finish, markdown=final_reply)
                        completed = True
                if done_data is None:
                    raise RuntimeError("流式回复未完成")
                traces.add(
                    "im_chat_stream",
                    user_id,
                    session_id,
                    provider=done_data.get("provider", ""),
                    model=getattr(_engine, "model", ""),
                    duration_ms=int((time.perf_counter() - started) * 1000),
                    usage=done_data.get("usage"),
                    cost=done_data.get("cost", 0),
                    tools_used=done_data.get("tools_used"),
                )
                logger.info(
                    "流式回答 %s: %s -> %s",
                    user_id,
                    question[:30],
                    build_reply(done_data)[:60],
                )
        except Exception as e:  # noqa: BLE001
            logger.exception("处理消息失败")
            if card is not None and not completed:
                try:
                    await asyncio.to_thread(card.ai_fail)
                except Exception:  # noqa: BLE001
                    pass
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
    if not state.im_enabled.get("dingtalk", settings.dingtalk_bot_enabled):
        logger.info("钉钉机器人已禁用，跳过连接")
        return
    client = build_stream_client()
    logger.info("钉钉 Stream 机器人启动中...")
    client.start_forever()
