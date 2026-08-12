"""本地可观测性：把问答/上传等请求的链路信息落到 SQLite，供后台查看。"""
import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path


class TraceStore:
    def __init__(self, db_path: str = "data/traces.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS traces(
                id TEXT PRIMARY KEY,
                ts TEXT NOT NULL,
                request_type TEXT NOT NULL,
                user_id TEXT DEFAULT '',
                session_id TEXT DEFAULT '',
                provider TEXT DEFAULT '',
                model TEXT DEFAULT '',
                status TEXT NOT NULL,
                duration_ms INTEGER DEFAULT 0,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
                tools_used TEXT DEFAULT '[]',
                error TEXT DEFAULT ''
            )
            """
        )
        self._conn.commit()

    def add(
        self,
        request_type: str,
        user_id: str = "",
        session_id: str = "",
        provider: str = "",
        model: str = "",
        status: str = "success",
        duration_ms: int = 0,
        usage: dict | None = None,
        cost: float = 0,
        tools_used: list[str] | None = None,
        error: str = "",
    ) -> None:
        usage = usage or {}
        self._conn.execute(
            """
            INSERT INTO traces(
                id, ts, request_type, user_id, session_id, provider, model, status,
                duration_ms, prompt_tokens, completion_tokens, total_tokens, cost,
                tools_used, error
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                uuid.uuid4().hex[:12],
                datetime.now().isoformat(),
                request_type,
                user_id,
                session_id,
                provider,
                model,
                status,
                int(duration_ms),
                int(usage.get("prompt_tokens", 0) or 0),
                int(usage.get("completion_tokens", 0) or 0),
                int(usage.get("total_tokens", 0) or 0),
                float(cost or 0),
                json.dumps(tools_used or [], ensure_ascii=False),
                error or "",
            ),
        )
        self._conn.commit()

    def list(self, limit: int = 200) -> list[dict]:
        rows = self._conn.execute(
            "SELECT id, ts, request_type, user_id, session_id, provider, model, status,"
            " duration_ms, prompt_tokens, completion_tokens, total_tokens, cost,"
            " tools_used, error FROM traces ORDER BY rowid DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "ts": r[1],
                "request_type": r[2],
                "user_id": r[3],
                "session_id": r[4],
                "provider": r[5],
                "model": r[6],
                "status": r[7],
                "duration_ms": r[8],
                "prompt_tokens": r[9],
                "completion_tokens": r[10],
                "total_tokens": r[11],
                "cost": r[12],
                "tools_used": json.loads(r[13] or "[]"),
                "error": r[14],
            }
            for r in rows
        ]
