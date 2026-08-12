"""企业微信机器人适配：URL 验证、回调解密、主动回复。"""
import base64
import hashlib
import logging
import struct
import time
import xml.etree.ElementTree as ET

import httpx
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.agent.qa import QaEngine
from app.config import settings
from app.im.common import build_reply, clean_mention
from app.state import index, sessions, traces

logger = logging.getLogger("xiaosu.wecom")

router = APIRouter(prefix="/api/im/wecom", tags=["wecom"])
_engine = QaEngine(index, sessions)
_token_cache = {"token": "", "expires_at": 0}


def get_access_token() -> str:
    """获取企业微信 access_token，带本地缓存。"""
    now = time.time()
    if _token_cache["token"] and _token_cache["expires_at"] > now + 60:
        return _token_cache["token"]
    resp = httpx.get(
        "https://qyapi.weixin.qq.com/cgi-bin/gettoken",
        params={
            "corpid": settings.wecom_corp_id,
            "corpsecret": settings.wecom_secret,
        },
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"企业微信 access_token 获取失败: {data}")
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = now + int(data.get("expires_in", 7200))
    return _token_cache["token"]


def send_wecom_text(target: str, content: str, target_type: str = "user") -> None:
    """通过企业微信 API 主动发送文本消息。"""
    token = get_access_token()
    body: dict = {
        "msgtype": "text",
        "text": {"content": content},
    }
    if target_type == "group":
        body["chatid"] = target
    else:
        body["touser"] = target
        body["agentid"] = int(settings.wecom_agent_id or 0)
    resp = httpx.post(
        "https://qyapi.weixin.qq.com/cgi-bin/message/send",
        params={"access_token": token},
        json=body,
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("errcode", 0) != 0:
        raise RuntimeError(f"企业微信消息发送失败: {data}")


def verify_signature(token: str, timestamp: str, nonce: str, encrypt: str, signature: str) -> bool:
    raw = "".join(sorted([token, timestamp, nonce, encrypt]))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest() == signature


def _pkcs7_unpad(data: bytes) -> bytes:
    pad = data[-1]
    if pad < 1 or pad > 16:
        raise ValueError("invalid padding")
    return data[:-pad]


def decrypt_message(encrypt: str, token: str, aes_key: str, corpid: str) -> str:
    """解密企业微信回调密文，返回内部 XML。"""
    key = base64.b64decode(aes_key + "=")
    iv = key[:16]
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    decryptor = cipher.decryptor()
    plain = _pkcs7_unpad(decryptor.update(base64.b64decode(encrypt)) + decryptor.finalize())
    msg_len = struct.unpack(">I", plain[16:20])[0]
    msg = plain[20 : 20 + msg_len].decode("utf-8")
    receive_id = plain[20 + msg_len :].decode("utf-8")
    if receive_id != corpid:
        raise ValueError("receive id mismatch")
    return msg


def _parse_callback(xml_text: str) -> dict:
    root = ET.fromstring(xml_text)

    def text(tag: str) -> str:
        node = root.find(tag)
        return node.text or "" if node is not None else ""

    return {
        "to_user": text("ToUserName"),
        "from_user": text("FromUserName"),
        "chat_id": text("ChatId"),
        "msg_type": text("MsgType"),
        "content": text("Content"),
        "agent_id": text("AgentID"),
    }


def handle_wecom_text(
    user_id: str,
    session_id: str,
    target: str,
    target_type: str,
    content: str,
) -> None:
    question = clean_mention(content)
    if not question:
        return
    started = time.perf_counter()
    try:
        result = _engine.answer(user_id, session_id, question)
        reply = build_reply(result)
        send_wecom_text(target, reply, target_type)
        traces.add(
            "wecom_chat",
            user_id,
            session_id,
            provider=result.get("provider", ""),
            model=getattr(_engine, "model", ""),
            duration_ms=int((time.perf_counter() - started) * 1000),
            usage=result.get("usage"),
            cost=result.get("cost", 0),
            tools_used=result.get("tools_used"),
        )
        logger.info("企业微信回答 %s: %s -> %s", user_id, question[:30], reply[:60])
    except Exception as e:  # noqa: BLE001
        logger.exception("企业微信处理消息失败")
        try:
            send_wecom_text(target, f"抱歉，处理你的问题出错了：{e}", target_type)
        except Exception:  # noqa: BLE001
            pass
        traces.add(
            "wecom_chat",
            user_id,
            session_id,
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(e),
        )


@router.get("")
def verify_url(
    msg_signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
    echostr: str = Query(""),
):
    """企业微信后台配置回调 URL 时的验证请求。"""
    if not verify_signature(
        settings.wecom_token, timestamp, nonce, echostr, msg_signature
    ):
        raise HTTPException(400, "signature mismatch")
    plain = decrypt_message(
        echostr, settings.wecom_token, settings.wecom_aes_key, settings.wecom_corp_id
    )
    return PlainTextResponse(plain)


@router.post("")
def callback(
    body: bytes = Body(...),
    msg_signature: str = Query(""),
    timestamp: str = Query(""),
    nonce: str = Query(""),
):
    """接收企业微信消息回调并主动回复。"""
    try:
        outer = ET.fromstring(body.decode("utf-8"))
        encrypt = outer.findtext("Encrypt") or ""
        sig = outer.findtext("MsgSignature") or msg_signature
        ts = outer.findtext("TimeStamp") or timestamp
        nc = outer.findtext("Nonce") or nonce
        if not verify_signature(settings.wecom_token, ts, nc, encrypt, sig):
            raise HTTPException(400, "signature mismatch")
        inner = decrypt_message(
            encrypt, settings.wecom_token, settings.wecom_aes_key, settings.wecom_corp_id
        )
        msg = _parse_callback(inner)
        if msg["msg_type"] == "text" and msg["content"]:
            user_id = msg["from_user"] or "unknown"
            if msg["chat_id"]:
                session_id = msg["chat_id"]
                target, target_type = msg["chat_id"], "group"
            else:
                session_id = user_id
                target, target_type = user_id, "user"
            handle_wecom_text(
                user_id, session_id, target, target_type, msg["content"]
            )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.exception("企业微信回调处理失败")
        raise HTTPException(500, str(e))
    return PlainTextResponse("success")
