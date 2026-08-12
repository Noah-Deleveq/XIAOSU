"""知识库 API：上传 / 列表 / 删除（增量更新：同名文件先清旧再重建）"""
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.knowledge.parser import parse_text
from app.state import docs, index

router = APIRouter(prefix="/api/docs", tags=["docs"])

SUPPORTED_EXT = {"md", "txt", "pdf", "docx"}


@router.get("")
def list_docs() -> dict:
    return {"docs": docs.list()}


@router.post("")
async def upload(file: UploadFile = File(...)) -> dict:
    name = file.filename or "unnamed"
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in SUPPORTED_EXT:
        raise HTTPException(400, f"不支持的格式: {ext}，支持 md/txt/pdf/docx")
    content = await file.read()
    try:
        text = parse_text(name, content)
    except Exception as e:
        raise HTTPException(400, f"解析失败: {e}")
    doc_id = str(uuid.uuid4())[:8]
    n = index.index_doc(doc_id, name, text)
    docs.upsert(doc_id, name, ext, "indexed")
    return {"id": doc_id, "name": name, "status": "indexed", "chunks": n}


@router.delete("/{doc_id}")
def delete_doc(doc_id: str) -> dict:
    if docs.get(doc_id) is None:
        raise HTTPException(404, "文档不存在")
    index.delete_doc(doc_id)
    docs.delete(doc_id)
    return {"ok": True}
