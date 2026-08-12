"""飞书机器人适配：WebSocket 长连接接收消息，AI 卡片流式回复，失败自动回退文本。"""
import json
import logging
import time
from typing import Any

from app.agent.qa import QaEngine
from app.config import settings
from app.im.common import build_reply, clean_mention
from app.state import index, sessions, traces

logger = logging.getLogger("xiaosu.feishu")

_engine = QaEngine(index, sessions)
_api_client: Any | None = None

STREAM_PATCH_MIN_SECONDS = 0.35
STREAM_PATCH_MIN_CHARS = 60


def get_api_client() -> Any:
    """复用同一个飞书 API 客户端用于主动回复。"""
    global _api_client
    if _api_client is None:
        import lark_oapi as lark

        _api_client = (
            lark.Client.builder()
            .app_id(settings.feishu_app_id)
            .app_secret(settings.feishu_app_secret)
            .log_level(lark.LogLevel.INFO)
            .build()
        )
    return _api_client


def _card_payload(markdown: str, footer: str = "") -> str:
    """生成飞书交互卡片的 JSON 内容。"""
    elements = [{"tag": "markdown", "content": markdown or "正在思考..."}]
    if footer:
        elements.append(
            {
                "tag": "note",
                "elements": [{"tag": "plain_text", "content": footer}],
            }
        )
    card = {
        "config": {"wide_screen_mode": True},
        "header": {
            "template": "blue",
            "title": {"tag": "plain_text", "content": "小苏"},
        },
        "elements": elements,
    }
    return json.dumps(card, ensure_ascii=False)


def _send_message(
    chat_id: str, msg_type: str, content: str, reply_to: str | None = None
) -> str:
    """发送飞书消息；优先回复原消息，失败时回退为会话新消息。"""
    from lark_oapi.api.im.v1 import (
        CreateMessageRequest,
        CreateMessageRequestBody,
        ReplyMessageRequest,
        ReplyMessageRequestBody,
    )

    if reply_to:
        reply_request = (
            ReplyMessageRequest.builder()
            .message_id(reply_to)
            .request_body(
                ReplyMessageRequestBody.builder()
                .msg_type(msg_type)
                .content(content)
                .build()
            )
            .build()
        )
        try:
            resp = get_api_client().im.v1.message.reply(reply_request)
        except Exception as e:  # noqa: BLE001
            logger.warning("飞书回复消息失败，回退新消息: %s", e)
            resp = None
        if resp is not None and resp.code == 0:
            data = getattr(resp, "data", None)
            message_id = (
                getattr(data, "message_id", "") if data is not None else ""
            )
            if message_id:
                return message_id
            logger.warning("飞书回复成功但未返回 message_id，回退新消息")
        if resp is not None:
            detail = getattr(resp, "msg", "") or ""
            logger.warning("飞书回复消息未成功，回退新消息: code=%s msg=%s", resp.code, detail)

    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type(msg_type)
            .content(content)
            .build()
        )
        .build()
    )
    resp = get_api_client().im.v1.message.create(request)
    if resp.code != 0:
        detail = getattr(resp, "msg", "") or ""
        raw = getattr(resp, "raw", None)
        raw_text = getattr(raw, "text", "") if raw is not None else ""
        raise RuntimeError(
            f"飞书消息发送失败: code={resp.code} msg={detail} raw={raw_text}"
        )
    data = getattr(resp, "data", None)
    return getattr(data, "message_id", "") if data is not None else ""


def send_feishu_text(
    chat_id: str, content: str, reply_to: str | None = None
) -> None:
    """向飞书会话发送文本消息。"""
    _send_message(
        chat_id,
        "text",
        json.dumps({"text": content}, ensure_ascii=False),
        reply_to,
    )


def send_feishu_card(
    chat_id: str, content: str, reply_to: str | None = None
) -> str:
    """发送交互卡片，返回 message_id 供后续流式更新。"""
    message_id = _send_message(chat_id, "interactive", content, reply_to)
    if not message_id:
        raise RuntimeError("飞书卡片发送成功但未返回 message_id")
    return message_id


def patch_feishu_card(message_id: str, content: str) -> None:
    """更新已发送的飞书交互卡片。"""
    from lark_oapi.api.im.v1 import PatchMessageRequest, PatchMessageRequestBody

    request = (
        PatchMessageRequest.builder()
        .message_id(message_id)
        .request_body(
            PatchMessageRequestBody.builder().content(content).build()
        )
        .build()
    )
    resp = get_api_client().im.v1.message.patch(request)
    if resp.code != 0:
        detail = getattr(resp, "msg", "") or ""
        raw = getattr(resp, "raw", None)
        raw_text = getattr(raw, "text", "") if raw is not None else ""
        raise RuntimeError(
            f"飞书卡片更新失败: code={resp.code} msg={detail} raw={raw_text}"
        )


class FeishuCard:
    """飞书 AI 卡片：增量更新内容，更新失败时保留文本回退。"""

    def __init__(self, chat_id: str, message_id: str) -> None:
        self.chat_id = chat_id
        self.message_id = message_id
        self.completed = False
        self.fallback_content = ""
        self._content = ""
        self._pending = ""
        self._last_patch = 0.0

    def ai_streaming(self, text: str) -> None:
        if not text:
            return
        self._content += text
        self._pending += text
        now = time.perf_counter()
        if (
            len(self._pending) >= STREAM_PATCH_MIN_CHARS
            or now - self._last_patch >= STREAM_PATCH_MIN_SECONDS
        ):
            self._flush()

    def ai_finish(self, markdown: str) -> None:
        self._content = markdown
        self._pending = ""
        try:
            patch_feishu_card(self.message_id, _card_payload(markdown, "生成完成"))
            self.fallback_content = ""
            self._last_patch = time.perf_counter()
        except Exception as e:  # noqa: BLE001
            self.fallback_content = markdown
            logger.warning("飞书卡片完成更新失败，回退文本: %s", e)
        self.completed = True

    def ai_fail(self) -> None:
        if self.completed:
            return
        text = self._content or "正在思考..."
        try:
            patch_feishu_card(self.message_id, _card_payload(text, "处理失败"))
            self.fallback_content = ""
            self._last_patch = time.perf_counter()
        except Exception as e:  # noqa: BLE001
            self.fallback_content = self.fallback_content or "抱歉，处理你的问题出错了。"
            logger.warning("飞书卡片失败提示更新失败: %s", e)

    def _flush(self) -> None:
        if not self._pending:
            return
        content = self._content
        self._pending = ""
        try:
            patch_feishu_card(self.message_id, _card_payload(content))
            self.fallback_content = ""
            self._last_patch = time.perf_counter()
        except Exception as e:  # noqa: BLE001
            self.fallback_content = self.fallback_content or content
            logger.warning("飞书卡片流式更新失败，继续生成并在结束时回退: %s", e)


def extract_text(data: Any) -> tuple[str, str, str, str] | None:
    """从飞书事件里提取 (user_id, chat_id, text, message_id)，非文本消息返回 None。"""
    event = data.event
    if event is None or event.message is None:
        return None
    msg = event.message
    if msg.message_type != "text":
        return None
    try:
        content = json.loads(msg.content or "{}").get("text", "")
    except json.JSONDecodeError:
        content = ""
    sender_id = ""
    if event.sender and event.sender.sender_id:
        sender_id = (
            event.sender.sender_id.open_id
            or event.sender.sender_id.user_id
            or event.sender.sender_id.union_id
            or ""
        )
    return sender_id, msg.chat_id or "", content or "", msg.message_id or ""


def handle_feishu_text(
    user_id: str, chat_id: str, content: str, message_id: str | None = None
) -> None:
    question = clean_mention(content)
    if not question:
        return
    started = time.perf_counter()
    card = None
    completed = False
    try:
        try:
            card = FeishuCard(
                chat_id,
                send_feishu_card(
                    chat_id,
                    _card_payload("正在思考...", "生成中"),
                    message_id,
                ),
            )
        except Exception as e:  # noqa: BLE001
            logger.warning("飞书卡片启动失败，回退文本回复: %s", e)
            card = None

        if card is None:
            result = _engine.answer(user_id, chat_id, question)
            reply = build_reply(result)
            send_feishu_text(chat_id, reply, message_id)
            traces.add(
                "feishu_chat",
                user_id,
                chat_id,
                provider=result.get("provider", ""),
                model=getattr(_engine, "model", ""),
                duration_ms=int((time.perf_counter() - started) * 1000),
                usage=result.get("usage"),
                cost=result.get("cost", 0),
                tools_used=result.get("tools_used"),
            )
            logger.info("飞书回答 %s: %s -> %s", user_id, question[:30], reply[:60])
            return

        done_data: dict | None = None
        for event in _engine.answer_stream(user_id, chat_id, question):
            if event["type"] == "text":
                card.ai_streaming(event["text"])
            elif event["type"] == "done":
                done_data = event["data"]
        if done_data is None:
            raise RuntimeError("飞书流式回复未完成")

        final_reply = build_reply(done_data)
        card.ai_finish(final_reply)
        if card.fallback_content:
            send_feishu_text(chat_id, card.fallback_content, message_id)
        completed = True
        traces.add(
            "feishu_chat_stream",
            user_id,
            chat_id,
            provider=done_data.get("provider", ""),
            model=getattr(_engine, "model", ""),
            duration_ms=int((time.perf_counter() - started) * 1000),
            usage=done_data.get("usage"),
            cost=done_data.get("cost", 0),
            tools_used=done_data.get("tools_used"),
        )
        logger.info(
            "飞书流式回答 %s: %s -> %s",
            user_id,
            question[:30],
            final_reply[:60],
        )
    except Exception as e:  # noqa: BLE001
        logger.exception("飞书处理消息失败")
        if card is not None and not completed:
            card.ai_fail()
        if card is None or card.fallback_content:
            fallback = card.fallback_content if card is not None else ""
            if not fallback:
                fallback = f"抱歉，处理你的问题出错了：{e}"
            try:
                send_feishu_text(chat_id, fallback, message_id)
            except Exception:  # noqa: BLE001
                pass
        traces.add(
            "feishu_chat",
            user_id,
            chat_id,
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(e),
        )


def on_message(data: Any) -> None:
    parsed = extract_text(data)
    event = data.event
    message = event.message if event is not None else None
    logger.info(
        "飞书收到事件: user=%s chat=%s type=%s content=%s",
        parsed[0] if parsed else (event.sender.sender_id.open_id if event and event.sender and event.sender.sender_id else ""),
        parsed[1] if parsed else (message.chat_id if message else ""),
        message.message_type if message else "",
        (parsed[2] if parsed else "")[:50],
    )
    if parsed is None:
        return
    user_id, chat_id, content, message_id = parsed
    if not chat_id or not content:
        return
    handle_feishu_text(user_id, chat_id, content, message_id)


def build_ws_client() -> Any:
    import lark_oapi as lark
    from lark_oapi.api.im.v1 import P2ImMessageReceiveV1
    from lark_oapi.event.dispatcher_handler import EventDispatcherHandler

    handler = (
        EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )
    return lark.ws.Client(
        app_id=settings.feishu_app_id,
        app_secret=settings.feishu_app_secret,
        event_handler=handler,
    )


def start_feishu_bot() -> None:
    """启动飞书长连接（阻塞，放独立线程运行）。"""
    if not settings.feishu_app_id or not settings.feishu_app_secret:
        logger.warning("未配置 FEISHU_APP_ID/SECRET，跳过飞书连接")
        return
    client = build_ws_client()
    logger.info("飞书机器人启动中...")
    client.start()
