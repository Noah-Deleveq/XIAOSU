"""小苏 · FastAPI 应用入口（一条命令启动：HTTP 服务 + 钉钉 Stream 机器人）"""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.agent.router import router as agent_router
from app.config import settings
from app.knowledge.router import router as knowledge_router
from app.mock_api.router import router as mock_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # 日志落盘（logs/app.log），钉钉/uvicorn/问答日志都会写入
    import logging
    from pathlib import Path

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "app.log", encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )

    # 启动钉钉 / 飞书机器人（长连接，独立线程）
    import threading

    from app.im.dingtalk_bot import start_dingtalk_bot
    from app.im.feishu_bot import start_feishu_bot
    from app.knowledge.seed import seed_builtin_docs

    if settings.auto_seed_on_start:
        seeded = seed_builtin_docs()
        if seeded:
            logging.getLogger("xiaosu").info("已自动导入 %d 篇种子文档", seeded)

    threading.Thread(target=start_dingtalk_bot, daemon=True).start()
    threading.Thread(target=start_feishu_bot, daemon=True).start()
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
    return {"ok": True, "service": "xiaosu", "env": settings.app_env, "version": "0.1.0"}

web_dist = Path(__file__).resolve().parents[2] / "web" / "dist"
if not web_dist.exists():
    web_dist = Path.cwd() / "web" / "dist"
if web_dist.exists():
    app.mount("/", StaticFiles(directory=web_dist, html=True), name="web")
