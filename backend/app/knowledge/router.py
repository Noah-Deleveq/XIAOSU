"""知识库 API：上传 / 列表 / 删除（增量更新：同名文件先清旧再重建）"""
import time
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.knowledge.parser import parse_text
from app.state import docs, index, traces

router = APIRouter(prefix="/api/docs", tags=["docs"])

SUPPORTED_EXT = {"md", "txt", "pdf", "docx"}


@router.get("")
def list_docs() -> dict:
    return {"docs": docs.list()}


@router.get("/{doc_id}/chunk/{chunk_index}")
def get_chunk(doc_id: str, chunk_index: int) -> dict:
    """按文档 id + 片段序号返回原文片段，供前端引用定位/高亮。"""
    text = index.get_chunk(doc_id, chunk_index)
    if text is None:
        raise HTTPException(404, "原文片段不存在")
    doc = docs.get(doc_id) or {}
    return {
        "doc_id": doc_id,
        "name": doc.get("name", doc_id),
        "chunk_index": chunk_index,
        "text": text,
    }


@router.post("")
async def upload(file: UploadFile = File(...)) -> dict:
    started = time.perf_counter()
    name = file.filename or "unnamed"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in SUPPORTED_EXT:
        raise HTTPException(400, f"不支持的格式: {ext}，支持 md/txt/pdf/docx")
    try:
        content = await file.read()
        text = parse_text(name, content)
    except Exception as e:
        traces.add(
            "upload",
            status="error",
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(e),
        )
        raise HTTPException(400, f"解析失败: {e}")
    doc_id = str(uuid.uuid4())[:8]
    n = index.index_doc(doc_id, name, text)
    docs.delete_by_name(name)
    docs.upsert(doc_id, name, ext, "indexed")
    traces.add(
        "upload",
        status="success",
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return {"id": doc_id, "name": name, "status": "indexed", "chunks": n}


@router.delete("/{doc_id}")
def delete_doc(doc_id: str) -> dict:
    if docs.get(doc_id) is None:
        raise HTTPException(404, "文档不存在")
    index.delete_doc(doc_id)
    docs.delete(doc_id)
    return {"ok": True}
