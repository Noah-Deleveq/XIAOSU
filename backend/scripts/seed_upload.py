import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
"""将 seed_docs 下的内置文档上传到知识库（供 seed_data.sh 调用）"""
import glob
import os
import uuid

from app.knowledge.parser import parse_text
from app.state import docs, index


def main() -> None:
    files = sorted(glob.glob("seed_docs/*"))
    if not files:
        print("seed_docs 目录为空，跳过")
        return
    for f in files:
        name = os.path.basename(f)
        with open(f, "rb") as fh:
            text = parse_text(name, fh.read())
        doc_id = str(uuid.uuid4())[:8]
        n = index.index_doc(doc_id, name, text)
        docs.upsert(doc_id, name, name.rsplit(".", 1)[-1].lower(), "indexed")
        print(f"  {name}: {n} chunks")
    print("seed 完成")


if __name__ == "__main__":
    main()
