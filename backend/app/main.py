"""小苏 · FastAPI 应用入口"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.knowledge.router import router as knowledge_router

app = FastAPI(title="小苏 AI 助手", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(knowledge_router)


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "xiaosu", "env": settings.app_env}
