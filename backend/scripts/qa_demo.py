"""演示脚本：载入 seed 知识库 → 用真实 DeepSeek 问答验收题（Windows/WSL 通用）"""
import glob
import os
import sys

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND)
os.chdir(_BACKEND)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

c = TestClient(app)

print("== 上传知识库文档 ==")
for f in sorted(glob.glob("seed_docs/*.md")):
    name = os.path.basename(f)
    with open(f, "rb") as fh:
        r = c.post("/api/docs", files={"file": (name, fh, "text/markdown")})
    print(f"  {name}: {r.json().get('status')} ({r.json().get('chunks')} chunks)")

print("\n== 真实问答（deepseek-v4-flash）==")
questions = [
    "员工每年有几天年假？",
    "报销发票需要什么材料？",
    "新人入职第一天要做哪些事？",
    "我们公司CEO的家庭住址是？",
]
for q in questions:
    r = c.post("/api/chat", json={"user_id": "u1", "session_id": "s1", "message": q})
    d = r.json()
    print(f"\nQ: {q}")
    print(f"A: {d['answer'][:250]}")
    print(f"   引用: {[x['name'] for x in d['references']]} | 拒答: {d['refused']}")
