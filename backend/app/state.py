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

# 运行时 LLM 供应商（默认取 .env 的 LLM_PROVIDER，可在 Web 后台切换，重启后恢复 .env 值）
current_provider: str = settings.llm_provider
