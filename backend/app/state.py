"""应用共享状态（单例）：所有模块共用同一份索引/会话/文档存储"""
from app.config import settings
from app.knowledge.indexer import VectorIndex
from app.knowledge.store import DocStore
from app.session.store import SessionStore

index = VectorIndex(f"{settings.data_dir}/chroma")
sessions = SessionStore(f"{settings.data_dir}/sessions.db")
docs = DocStore(f"{settings.data_dir}/docs.db")
