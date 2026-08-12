"""问答 / 日志 / 设置 API"""
from fastapi import APIRouter, HTTPException

from app.agent.qa import QaEngine
from app.config import settings
from app.schemas import ChatRequest, ProviderSwitch
from app import state
from app.state import index, sessions

router = APIRouter(tags=["chat"])

_engine = QaEngine(index, sessions)


@router.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    return _engine.answer(req.user_id, req.session_id, req.message)


@router.get("/api/logs")
def logs() -> dict:
    turns = sessions.list_turns()
    return {
        "logs": turns,
        "summary": {
            "turns": len(turns),
            "total_tokens": sum(t["total_tokens"] for t in turns),
            "total_cost": round(sum(t["cost"] for t in turns), 4),
        },
    }


@router.get("/api/settings")
def settings_get() -> dict:
    """查看可用供应商 / 当前激活 / 钉钉接入状态"""
    return {
        "providers": settings.provider_names(),
        "current": state.current_provider,
        "dingtalk_configured": bool(
            settings.dingtalk_app_key and settings.dingtalk_app_secret
        ),
    }


@router.post("/api/settings/provider")
def settings_set_provider(payload: ProviderSwitch) -> dict:
    """运行时切换 LLM 供应商（内存生效，重启后恢复 .env 的 LLM_PROVIDER）"""
    if payload.name not in settings.provider_names():
        raise HTTPException(400, f"未知供应商: {payload.name}")
    state.current_provider = payload.name
    return {"ok": True, "current": state.current_provider}
