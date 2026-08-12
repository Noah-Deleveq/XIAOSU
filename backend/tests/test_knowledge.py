import shutil
from pathlib import Path

shutil.rmtree("data", ignore_errors=True)  # 每个测试会话从干净数据开始

"""知识库功能测试：上传 → 索引 → 检索命中 → 删除 → 不再命中"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_TXT = """员工手册

第一章 年假

员工每年享有 10 天带薪年假，入职满一年后即可申请。

第二章 报销

报销发票需要提供：发票原件、报销单、审批通过截图。"""


def test_upload_and_search():
    """上传文档 → 检索能命中对应内容（带出处）"""
    r = client.post(
        "/api/docs",
        files={"file": ("员工手册.txt", SAMPLE_TXT.encode("utf-8"), "text/plain")},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "indexed"
    assert data["chunks"] > 0
    doc_id = data["id"]

    # 用 AppState 的搜索逻辑直接验证（等价于后续问答的检索）
    from app.knowledge.indexer import VectorIndex
    from app.config import settings

    idx = VectorIndex(f"{settings.data_dir}/chroma")
    hits = idx.search("员工每年几天年假")
    assert hits, "检索无结果"
    assert any("10 天" in h["text"] for h in hits), "未命中年假内容"
    assert all(h["doc_id"] == doc_id for h in hits), "出处 doc_id 不正确"

    # 列表包含该文档
    docs = client.get("/api/docs").json()["docs"]
    assert any(d["id"] == doc_id for d in docs)


def test_unsupported_format():
    """不支持的格式应返回 400"""
    r = client.post(
        "/api/docs",
        files={"file": ("evil.exe", b"MZ...", "application/octet-stream")},
    )
    assert r.status_code == 400


def test_delete_doc_removes_from_index():
    """删除文档后检索不再命中"""
    r = client.post(
        "/api/docs",
        files={"file": ("临时.txt", "临时内容：加班费按 1.5 倍计算".encode("utf-8"), "text/plain")},
    )
    doc_id = r.json()["id"]

    from app.knowledge.indexer import VectorIndex
    from app.config import settings

    idx = VectorIndex(f"{settings.data_dir}/chroma")
    assert any("加班费" in h["text"] for h in idx.search("加班费怎么算"))

    assert client.delete(f"/api/docs/{doc_id}").status_code == 200
    idx2 = VectorIndex(f"{settings.data_dir}/chroma")
    assert not any("加班费" in h["text"] for h in idx2.search("加班费怎么算"))
