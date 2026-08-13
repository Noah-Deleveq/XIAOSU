"""内置种子文档导入：启动时自动补齐缺失文档，保证 Demo 开箱即用。"""
import logging
import uuid
from pathlib import Path

from app.knowledge.parser import parse_text
from app.state import docs, index

logger = logging.getLogger("xiaosu.seed")

SEED_DIR = Path(__file__).resolve().parents[2] / "seed_docs"
SUPPORTED_EXT = {"md", "txt", "pdf", "docx"}


def seed_builtin_docs() -> int:
    """导入 seed_docs 下尚未入库的内置文档，返回导入篇数。"""
    if not SEED_DIR.is_dir():
        logger.warning("未找到 seed_docs 目录，跳过自动导入: %s", SEED_DIR)
        return 0

    existing_names = {doc["name"] for doc in docs.list()}
    count = 0
    for path in sorted(SEED_DIR.iterdir()):
        if not path.is_file():
            continue
        if path.name in existing_names:
            continue
        ext = path.suffix.lower().lstrip(".")
        if ext not in SUPPORTED_EXT:
            continue
        try:
            text = parse_text(path.name, path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            logger.warning("内置文档解析失败: %s (%s)", path.name, exc)
            continue
        doc_id = str(uuid.uuid4())[:8]
        n = index.index_doc(doc_id, path.name, text)
        docs.delete_by_name(path.name)
        docs.upsert(doc_id, path.name, ext, "indexed")
        logger.info("自动导入种子文档: %s (%d chunks)", path.name, n)
        count += 1
    return count
