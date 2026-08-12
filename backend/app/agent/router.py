"""问答与日志 API"""
from fastapi import APIRouter

from app.agent.qa import QaEngine
from app.schemas import ChatRequest
from app.state import index, sessions

router = APIRouter(tags=["chat"])

_engine = QaEngine(index, sessions)


@router.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    return _engine.answer(req.user_id, req.session_id, req.message)


@router.get("/api/logs")
def logs() -> dict:
    return {"logs": sessions.list_sessions()}
