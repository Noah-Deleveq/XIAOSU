"""切块 + 本地 BM25 检索（jieba 分词，零外部模型下载，离线可用）

说明：笔试数据量小（几 MB 文档），BM25 关键词检索完全够用，
且不依赖任何 embedding 模型下载，面试现场断网也能跑。
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

import jieba

CHUNK_SIZE = 600
OVERLAP = 100
_STOPWORDS = set("的了是在和有与就都而及于这那之吗呢吧啊呀我们你们他们一个什么没有也不把被从向对".strip())


def chunk_text(text: str, size: int = CHUNK_SIZE) -> list[str]:
    """按段落切块，超长段落截断并保留重叠，避免切断语义"""
    paras = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        while len(p) > size:
            if buf:
                chunks.append(buf)
                buf = ""
            chunks.append(p[:size])
            p = p[size - OVERLAP:]
        if len(buf) + len(p) + 2 > size:
            if buf:
                chunks.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    return chunks


def _tokenize(text: str) -> list[str]:
    return [
        w
        for w in jieba.cut(text)
        if w.strip() and w not in _STOPWORDS and not re.fullmatch(r"\s+", w)
    ]


class VectorIndex:
    """BM25 检索索引，JSON 持久化到 data/chroma/index.json"""

    def __init__(self, persist_dir: str = "data/chroma") -> None:
        self._path = Path(persist_dir) / "index.json"
        self._chunks: dict[str, str] = {}
        self._meta: dict[str, dict] = {}
        self._doc_chunks: dict[str, list[str]] = {}
        self._doc_names: dict[str, str] = {}
        self._load()

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            data = json.loads(self._path.read_text("utf-8"))
            self._chunks = data["chunks"]
            self._meta = data["meta"]
            self._doc_chunks = data["doc_chunks"]
            self._doc_names = data["doc_names"]
        except Exception:
            pass

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(
                {
                    "chunks": self._chunks,
                    "meta": self._meta,
                    "doc_chunks": self._doc_chunks,
                    "doc_names": self._doc_names,
                },
                ensure_ascii=False,
            ),
            "utf-8",
        )

    def index_doc(self, doc_id: str, name: str, text: str) -> int:
        """索引文档；同名文档先清旧（增量替换），同 id 也清旧"""
        self.delete_doc(doc_id)
        for old_id, old_name in list(self._doc_names.items()):
            if old_name == name and old_id != doc_id:
                self.delete_doc(old_id)
        chunks = chunk_text(text)
        if not chunks:
            return 0
        chunk_ids: list[str] = []
        for i, c in enumerate(chunks):
            cid = f"{doc_id}#{i}"
            self._chunks[cid] = c
            self._meta[cid] = {"doc_id": doc_id, "name": name, "chunk_index": i}
            chunk_ids.append(cid)
        self._doc_chunks[doc_id] = chunk_ids
        self._doc_names[doc_id] = name
        self._save()
        return len(chunks)

    def delete_doc(self, doc_id: str) -> None:
        ids = self._doc_chunks.pop(doc_id, [])
        for cid in ids:
            self._chunks.pop(cid, None)
            self._meta.pop(cid, None)
        self._doc_names.pop(doc_id, None)
        self._save()

    def get_chunk(self, doc_id: str, chunk_index: int) -> str | None:
        """按文档 id + 片段序号取原文片段，供引用定位使用。"""
        return self._chunks.get(f"{doc_id}#{chunk_index}")

    def search(self, query: str, k: int = 4) -> list[dict]:
        """BM25 检索，返回带出处（doc_id/name/chunk_index）的片段"""
        if not self._chunks:
            return []
        q_terms = Counter(_tokenize(query))
        n = len(self._chunks)
        df: Counter = Counter()
        for text in self._chunks.values():
            for w in set(_tokenize(text)):
                df[w] += 1
        idf = {w: math.log(1 + (n - df[w] + 0.5) / (df[w] + 0.5)) for w in q_terms}

        scored: list[tuple[float, str]] = []
        for cid, text in self._chunks.items():
            tf = Counter(_tokenize(text))
            score = sum(
                q_terms[w] * idf.get(w, 0) * (tf[w] / (tf[w] + 1)) for w in q_terms
            )
            if score > 0:
                scored.append((score, cid))
        scored.sort(key=lambda x: -x[0])

        out = []
        for _, cid in scored[:k]:
            m = self._meta[cid]
            out.append(
                {
                    "text": self._chunks[cid],
                    "doc_id": m["doc_id"],
                    "name": m["name"],
                    "chunk_index": m["chunk_index"],
                }
            )
        return out
