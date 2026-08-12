"""企业微信回调验证、解密与消息处理测试"""
import base64
import os
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from fastapi.testclient import TestClient

from app.config import settings
from app.im import wecom_bot
from app.main import app

client = TestClient(app)


def _make_aes_key() -> str:
    return base64.b64encode(os.urandom(32)).decode().rstrip("=")


def _encrypt_message(msg: str, aes_key: str, corpid: str) -> str:
    key = base64.b64decode(aes_key + "=")
    iv = key[:16]
    msg_bytes = msg.encode("utf-8")
    plain = (
        os.urandom(16)
        + struct.pack(">I", len(msg_bytes))
        + msg_bytes
        + corpid.encode("utf-8")
    )
    pad = 16 - len(plain) % 16
    plain += bytes([pad]) * pad
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    return base64.b64encode(encryptor.update(plain) + encryptor.finalize()).decode()


def _sign(token: str, timestamp: str, nonce: str, encrypt: str) -> str:
    import hashlib

    raw = "".join(sorted([token, timestamp, nonce, encrypt]))
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def _configure_wecom(monkeypatch, aes_key: str) -> None:
    monkeypatch.setattr(settings, "wecom_corp_id", "corp123")
    monkeypatch.setattr(settings, "wecom_agent_id", "1000002")
    monkeypatch.setattr(settings, "wecom_secret", "secret")
    monkeypatch.setattr(settings, "wecom_token", "token123")
    monkeypatch.setattr(settings, "wecom_aes_key", aes_key)


def test_wecom_url_verify(monkeypatch):
    """企业微信后台 URL 验证：签名正确时返回解密后的 echostr"""
    aes_key = _make_aes_key()
    _configure_wecom(monkeypatch, aes_key)
    timestamp = "1700000000"
    nonce = "nonce123"
    encrypt = _encrypt_message("hello-xiaosu", aes_key, "corp123")
    sig = _sign("token123", timestamp, nonce, encrypt)

    r = client.get(
        "/api/im/wecom",
        params={
            "msg_signature": sig,
            "timestamp": timestamp,
            "nonce": nonce,
            "echostr": encrypt,
        },
    )
    assert r.status_code == 200
    assert r.text == "hello-xiaosu"


def test_wecom_url_verify_bad_signature(monkeypatch):
    """企业微信 URL 验证：签名错误应拒绝"""
    aes_key = _make_aes_key()
    _configure_wecom(monkeypatch, aes_key)
    encrypt = _encrypt_message("hello", aes_key, "corp123")
    r = client.get(
        "/api/im/wecom",
        params={
            "msg_signature": "bad",
            "timestamp": "1700000000",
            "nonce": "nonce123",
            "echostr": encrypt,
        },
    )
    assert r.status_code == 400


class _WecomEngine:
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


def test_wecom_callback_text(monkeypatch):
    """企业微信收到文本消息后调用小苏回答并主动发送回复"""
    aes_key = _make_aes_key()
    _configure_wecom(monkeypatch, aes_key)
    monkeypatch.setattr(wecom_bot, "_engine", _WecomEngine())
    sent = []
    monkeypatch.setattr(
        wecom_bot,
        "send_wecom_text",
        lambda target, content, target_type="user": sent.append((target, content, target_type)),
    )

    inner_xml = """<xml>
        <ToUserName>corp123</ToUserName>
        <FromUserName>user001</FromUserName>
        <CreateTime>1700000000</CreateTime>
        <MsgType>text</MsgType>
        <Content>@小苏 员工每年几天年假？</Content>
        <MsgId>msg1</MsgId>
        <AgentID>1000002</AgentID>
    </xml>"""
    encrypt = _encrypt_message(inner_xml, aes_key, "corp123")
    timestamp = "1700000000"
    nonce = "nonce123"
    sig = _sign("token123", timestamp, nonce, encrypt)
    outer_xml = f"""<xml>
        <ToUserName>corp123</ToUserName>
        <AgentID>1000002</AgentID>
        <Encrypt><![CDATA[{encrypt}]]></Encrypt>
    </xml>"""

    r = client.post(
        "/api/im/wecom",
        params={"msg_signature": sig, "timestamp": timestamp, "nonce": nonce},
        content=outer_xml.encode("utf-8"),
        headers={"Content-Type": "text/xml"},
    )
    assert r.status_code == 200
    assert r.text == "success"
    assert sent and sent[0][0] == "user001"
    assert "10 天带薪年假" in sent[0][1]
    assert "员工手册.md" in sent[0][1]
