"""问答 / 日志 / 设置 API"""
import json
import time

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from app.agent.qa import LLMUnavailableError, QaEngine
from app.config import settings
from app.knowledge.indexer import chunk_text
from app.knowledge.parser import parse_text
from app.schemas import ChatRequest, ProviderSwitch
from app import state
from app.state import index, sessions, traces

router = APIRouter(tags=["chat"])

_engine = QaEngine(index, sessions)

MAX_FILE_CHUNKS = 8


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _file_hits(name: str, content: str) -> list[dict]:
    """把用户上传的文件切成片段，作为本次问答的临时引用来源。"""
    return [
        {
            "name": name,
            "text": chunk,
            "doc_id": f"upload:{name}",
            "chunk_index": i,
        }
        for i, chunk in enumerate(chunk_text(content)[:MAX_FILE_CHUNKS])
    ]


def _degraded_response(user_id: str, session_id: str, message: str) -> dict:
    return {
        "answer": "抱歉，模型服务暂时不可用，请稍后再试。",
        "references": [],
        "refused": True,
        "used_tool": False,
        "tools_used": [],
        "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        "cost": 0,
        "provider": state.current_provider,
        "session_id": session_id,
        "degraded": True,
        "detail": message,
    }


@router.post("/api/chat")
def chat(req: ChatRequest) -> dict:
    started = time.perf_counter()
    try:
        result = _engine.answer(req.user_id, req.session_id, req.message)
        traces.add(
            "chat",
            req.user_id,
            req.session_id,
            provider=result.get("provider", ""),
            model=getattr(_engine, "model", ""),
            duration_ms=int((time.perf_counter() - started) * 1000),
            usage=result.get("usage"),
            cost=result.get("cost", 0),
            tools_used=result.get("tools_used"),
        )
        return result
    except LLMUnavailableError as e:
        traces.add(
            "chat",
            req.user_id,
            req.session_id,
            provider=state.current_provider,
            model=getattr(_engine, "model", ""),
            status="degraded",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(e),
        )
        return _degraded_response(req.user_id, req.session_id, str(e))
    except Exception as e:  # noqa: BLE001
        traces.add(
            "chat",
            req.user_id,
            req.session_id,
            provider=state.current_provider,
            model=getattr(_engine, "model", ""),
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(e),
        )
        return _degraded_response(req.user_id, req.session_id, str(e))


@router.post("/api/chat/stream")
def chat_stream(req: ChatRequest):
    """SSE 流式问答：边生成边返回 token，结束后返回引用/Token/成本等元数据。"""

    def gen():
        started = time.perf_counter()
        done_data: dict | None = None
        try:
            for event in _engine.answer_stream(req.user_id, req.session_id, req.message):
                if event["type"] == "text":
                    yield _sse("token", event)
                elif event["type"] == "tool":
                    yield _sse("tool", event)
                elif event["type"] == "done":
                    done_data = event["data"]
                    yield _sse("done", event["data"])
            traces.add(
                "chat_stream",
                req.user_id,
                req.session_id,
                provider=(done_data or {}).get("provider", ""),
                model=getattr(_engine, "model", ""),
                duration_ms=int((time.perf_counter() - started) * 1000),
                usage=(done_data or {}).get("usage"),
                cost=(done_data or {}).get("cost", 0),
                tools_used=(done_data or {}).get("tools_used"),
            )
        except Exception as e:  # noqa: BLE001
            traces.add(
                "chat_stream",
                req.user_id,
                req.session_id,
                provider=state.current_provider,
                model=getattr(_engine, "model", ""),
                status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=str(e),
            )
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/api/chat/file")
async def chat_file(
    file: UploadFile = File(...),
    question: str = Form(...),
    user_id: str = Form("web-admin"),
    session_id: str = Form("web-demo"),
) -> dict:
    """上传文件后针对文件内容问答（一次性返回）。"""
    question = question.strip()
    if not question:
        raise HTTPException(400, "问题不能为空")
    name = file.filename or "unnamed.txt"
    content = await file.read()
    try:
        text = parse_text(name, content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"文件解析失败: {e}")

    hits = _file_hits(name, text)
    started = time.perf_counter()
    try:
        result = _engine.answer(user_id, session_id, question, manual_hits=hits)
        traces.add(
            "chat_file",
            user_id,
            session_id,
            provider=result.get("provider", ""),
            model=getattr(_engine, "model", ""),
            duration_ms=int((time.perf_counter() - started) * 1000),
            usage=result.get("usage"),
            cost=result.get("cost", 0),
            tools_used=result.get("tools_used"),
        )
        return result
    except Exception as e:  # noqa: BLE001
        traces.add(
            "chat_file",
            user_id,
            session_id,
            provider=state.current_provider,
            model=getattr(_engine, "model", ""),
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(e),
        )
        raise


@router.post("/api/chat/file/stream")
async def chat_file_stream(
    file: UploadFile = File(...),
    question: str = Form(...),
    user_id: str = Form("web-admin"),
    session_id: str = Form("web-demo"),
):
    """上传文件后针对文件内容流式问答。"""
    question = question.strip()
    if not question:
        raise HTTPException(400, "问题不能为空")
    name = file.filename or "unnamed.txt"
    content = await file.read()
    try:
        text = parse_text(name, content)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"文件解析失败: {e}")
    hits = _file_hits(name, text)

    def gen():
        started = time.perf_counter()
        done_data: dict | None = None
        try:
            for event in _engine.answer_stream(
                user_id, session_id, question, manual_hits=hits
            ):
                if event["type"] == "text":
                    yield _sse("token", event)
                elif event["type"] == "tool":
                    yield _sse("tool", event)
                elif event["type"] == "done":
                    done_data = event["data"]
                    yield _sse("done", event["data"])
            traces.add(
                "chat_file_stream",
                user_id,
                session_id,
                provider=(done_data or {}).get("provider", ""),
                model=getattr(_engine, "model", ""),
                duration_ms=int((time.perf_counter() - started) * 1000),
                usage=(done_data or {}).get("usage"),
                cost=(done_data or {}).get("cost", 0),
                tools_used=(done_data or {}).get("tools_used"),
            )
        except Exception as e:  # noqa: BLE001
            traces.add(
                "chat_file_stream",
                user_id,
                session_id,
                provider=state.current_provider,
                model=getattr(_engine, "model", ""),
                status="error",
                duration_ms=int((time.perf_counter() - started) * 1000),
                error=str(e),
            )
            yield _sse("error", {"message": str(e)})

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/api/traces")
def traces_list() -> dict:
    """最近请求链路（可观测性）"""
    return {"traces": traces.list()}


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
        "wecom_configured": bool(
            settings.wecom_corp_id
            and settings.wecom_agent_id
            and settings.wecom_secret
            and settings.wecom_token
            and settings.wecom_aes_key
        ),
        "feishu_configured": bool(
            settings.feishu_app_id and settings.feishu_app_secret
        ),
    }


@router.post("/api/settings/provider")
def settings_set_provider(payload: ProviderSwitch) -> dict:
    """运行时切换 LLM 供应商（内存生效，重启后恢复 .env 的 LLM_PROVIDER）"""
    if payload.name not in settings.provider_names():
        raise HTTPException(400, f"未知供应商: {payload.name}")
    state.current_provider = payload.name
    return {"ok": True, "current": state.current_provider}
