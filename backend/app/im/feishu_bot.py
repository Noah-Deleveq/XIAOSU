"""飞书机器人适配：WebSocket 长连接接收消息，文本回复。"""
import json
import logging
import time
from collections import deque
from typing import Any

from app.agent.qa import LLMUnavailableError, QaEngine
from app.config import settings
from app.im.common import build_reply, clean_mention
from app.state import index, sessions, traces

logger = logging.getLogger("xiaosu.feishu")

_engine = QaEngine(index, sessions)
_api_client: Any | None = None
_seen_message_ids: set[str] = set()
_seen_message_order: deque[str] = deque()


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


def send_feishu_text(chat_id: str, content: str) -> None:
    """向飞书会话发送文本消息。"""
    from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(
            CreateMessageRequestBody.builder()
            .receive_id(chat_id)
            .msg_type("text")
            .content(json.dumps({"text": content}, ensure_ascii=False))
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


def extract_text(data: Any) -> tuple[str, str, str] | None:
    """从飞书事件里提取 (user_id, chat_id, text)，非文本消息返回 None。"""
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
    return sender_id, msg.chat_id or "", content or ""


def handle_feishu_text(user_id: str, chat_id: str, content: str) -> None:
    question = clean_mention(content)
    if not question:
        return
    started = time.perf_counter()
    try:
        try:
            result = _engine.answer(user_id, chat_id, question)
        except LLMUnavailableError:
            logger.warning("飞书首次模型调用失败，1 秒后重试")
            time.sleep(1.0)
            result = _engine.answer(user_id, chat_id, question)
        reply = build_reply(result)
        send_feishu_text(chat_id, reply)
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
    except Exception as e:  # noqa: BLE001
        logger.exception("飞书处理消息失败")
        try:
            send_feishu_text(chat_id, f"抱歉，处理你的问题出错了：{e}")
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
    message_id = message.message_id if message is not None else ""
    if message_id:
        if message_id in _seen_message_ids:
            logger.info("忽略重复飞书事件: %s", message_id)
            return
        _seen_message_ids.add(message_id)
        _seen_message_order.append(message_id)
        if len(_seen_message_order) > 500:
            _seen_message_ids.discard(_seen_message_order.popleft())
    user_id, chat_id, content = parsed
    if not chat_id or not content:
        return
    handle_feishu_text(user_id, chat_id, content)


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
