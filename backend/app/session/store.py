"""会话存储（SQLite）：按 user_id + session_id 保存对话历史，隔离上下文"""
import sqlite3
from datetime import datetime
from pathlib import Path


class SessionStore:
    def __init__(self, db_path: str = "data/sessions.db") -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                ts TEXT NOT NULL
            )
            """
        )
        self._conn.commit()

    def get_messages(self, user_id: str, session_id: str, limit: int = 20) -> list[dict]:
        rows = self._conn.execute(
            "SELECT role, content FROM messages WHERE user_id=? AND session_id=? ORDER BY id DESC LIMIT ?",
            (user_id, session_id, limit),
        ).fetchall()
        return [{"role": r[0], "content": r[1]} for r in reversed(rows)]

    def append(self, user_id: str, session_id: str, question: str, answer: str) -> None:
        now = datetime.now().isoformat()
        self._conn.execute(
            "INSERT INTO messages(user_id, session_id, role, content, ts) VALUES(?,?,?,?,?)",
            (user_id, session_id, "user", question, now),
        )
        self._conn.execute(
            "INSERT INTO messages(user_id, session_id, role, content, ts) VALUES(?,?,?,?,?)",
            (user_id, session_id, "assistant", answer, now),
        )
        self._conn.commit()

    def list_sessions(self) -> list[dict]:
        """全部会话记录（Web 后台对话日志用）"""
        rows = self._conn.execute(
            "SELECT user_id, session_id, role, content, ts FROM messages ORDER BY id"
        ).fetchall()
        return [
            {
                "user_id": r[0],
                "session_id": r[1],
                "role": r[2],
                "content": r[3],
                "ts": r[4],
            }
            for r in rows
        ]
