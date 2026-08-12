"""文档元数据存储（SQLite）：记录已上传文档及索引状态"""
import sqlite3
from datetime import datetime
from pathlib import Path


class DocStore:
    def __init__(self, db_path: str = "data/docs.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS docs(
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                ext TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'pending',
                updated_at TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def list(self) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, name, ext, status, updated_at FROM docs ORDER BY updated_at DESC"
        ).fetchall()
        return [
            {"id": r[0], "name": r[1], "ext": r[2], "status": r[3], "updated_at": r[4]}
            for r in rows
        ]

    def get(self, doc_id: str) -> dict | None:
        row = self._conn.execute(
            "SELECT id, name, ext, status, updated_at FROM docs WHERE id = ?", (doc_id,)
        ).fetchone()
        if row is None:
            return None
        return {"id": row[0], "name": row[1], "ext": row[2], "status": row[3], "updated_at": row[4]}

    def upsert(self, doc_id: str, name: str, ext: str, status: str) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO docs(id, name, ext, status, updated_at) VALUES(?,?,?,?,?)",
            (doc_id, name, ext, status, datetime.now().isoformat()),
        )
        self._conn.commit()

    def set_status(self, doc_id: str, status: str) -> None:
        self._conn.execute(
            "UPDATE docs SET status = ?, updated_at = ? WHERE id = ?",
            (status, datetime.now().isoformat(), doc_id),
        )
        self._conn.commit()

    def delete(self, doc_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM docs WHERE id = ?", (doc_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def delete_by_name(self, name: str) -> None:
        """删除同名旧文档记录（增量更新时使用，避免后台列表残留重复项）"""
        self._conn.execute("DELETE FROM docs WHERE name = ?", (name,))
        self._conn.commit()
