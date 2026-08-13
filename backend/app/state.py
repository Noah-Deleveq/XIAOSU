"""应用共享状态（单例）：所有模块共用同一份索引/会话/文档存储"""
from app.config import settings
from app.knowledge.indexer import VectorIndex
from app.knowledge.store import DocStore
from app.session.store import SessionStore
from app.trace.store import TraceStore

index = VectorIndex(f"{settings.data_dir}/chroma")
sessions = SessionStore(f"{settings.data_dir}/sessions.db")
docs = DocStore(f"{settings.data_dir}/docs.db")
traces = TraceStore(f"{settings.data_dir}/traces.db")

current_provider: str = settings.llm_provider if settings.llm_provider in settings.provider_names() else "deepseek"

# IM 机器人运行开关：默认跟随 .env，可在运行时通过 /api/im/toggle 切换
im_enabled: dict[str, bool] = {
    "dingtalk": settings.dingtalk_bot_enabled,
    "feishu": settings.feishu_bot_enabled,
}


def set_im_enabled(channel: str, enabled: bool) -> None:
    if channel not in im_enabled:
        raise ValueError(f"未知 IM 通道: {channel}")
    im_enabled[channel] = bool(enabled)
