"""小苏 · FastAPI 应用入口（一条命令启动：HTTP 服务 + 钉钉 Stream 机器人）"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.agent.router import router as agent_router
from app.config import settings
from app.knowledge.router import router as knowledge_router
from app.mock_api.router import router as mock_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 启动钉钉 Stream 机器人（长连接，独立线程）
    import threading

    from app.im.dingtalk_bot import start_dingtalk_bot

    threading.Thread(target=start_dingtalk_bot, daemon=True).start()
    yield


app = FastAPI(title="小苏 AI 助手", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge_router)
app.include_router(agent_router)
app.include_router(mock_router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "xiaosu", "env": settings.app_env}
