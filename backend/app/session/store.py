"""会话存储（SQLite）：按 user_id + session_id 保存对话历史与轮次日志，隔离上下文"""
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
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turn_logs(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT NOT NULL,
                used_tool INTEGER DEFAULT 0,
                refused INTEGER DEFAULT 0,
                provider TEXT DEFAULT '',
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                cost REAL DEFAULT 0,
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

    def log_turn(
        self,
        user_id: str,
        session_id: str,
        question: str,
        answer: str,
        used_tool: bool,
        refused: bool,
        provider: str,
        usage: dict,
        cost: float,
    ) -> None:
        """记录一轮问答（含 Token/成本/工具，Web 后台日志用）"""
        self._conn.execute(
            """
            INSERT INTO turn_logs(
                user_id, session_id, question, answer, used_tool, refused,
                provider, prompt_tokens, completion_tokens, total_tokens, cost, ts
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                user_id,
                session_id,
                question,
                answer,
                int(used_tool),
                int(refused),
                provider,
                usage.get("prompt_tokens", 0),
                usage.get("completion_tokens", 0),
                usage.get("total_tokens", 0),
                cost,
                datetime.now().isoformat(),
            ),
        )
        self._conn.commit()

    def list_sessions(self) -> list[dict]:
        """全部会话消息（按时间正序）"""
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

    def list_turns(self) -> list[dict]:
        """全部轮次日志（含 Token/成本/工具）"""
        rows = self._conn.execute(
            "SELECT user_id, session_id, question, answer, used_tool, refused, provider,"
            " prompt_tokens, completion_tokens, total_tokens, cost, ts FROM turn_logs ORDER BY id"
        ).fetchall()
        return [
            {
                "user_id": r[0],
                "session_id": r[1],
                "question": r[2],
                "answer": r[3],
                "used_tool": bool(r[4]),
                "refused": bool(r[5]),
                "provider": r[6],
                "prompt_tokens": r[7],
                "completion_tokens": r[8],
                "total_tokens": r[9],
                "cost": r[10],
                "ts": r[11],
            }
            for r in rows
        ]
