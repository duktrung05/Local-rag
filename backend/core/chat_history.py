import sqlite3
import json
import uuid
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from core.config import settings

logger = logging.getLogger(__name__)


def init_db():
    with sqlite3.connect(settings.sqlite_db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                message_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                sources TEXT DEFAULT '[]',
                provider TEXT DEFAULT '',
                created_at TEXT NOT NULL,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv ON messages(conversation_id)")
        conn.commit()
    logger.info(f"SQLite DB khởi tạo: {settings.sqlite_db_path}")


@contextmanager
def get_db():
    conn = sqlite3.connect(settings.sqlite_db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def create_conversation(title: str = "Cuộc trò chuyện mới") -> Dict:
    cid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?,?,?,?)",
            (cid, title, now, now)
        )
        conn.commit()
    return {"id": cid, "title": title, "created_at": now, "updated_at": now, "message_count": 0}


def get_conversations(limit: int = 50) -> List[Dict]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_conversation(conv_id: str) -> Optional[Dict]:
    with get_db() as conn:
        row = conn.execute("SELECT * FROM conversations WHERE id=?", (conv_id,)).fetchone()
    return dict(row) if row else None


def delete_conversation(conv_id: str) -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM messages WHERE conversation_id=?", (conv_id,))
        rows = conn.execute("DELETE FROM conversations WHERE id=?", (conv_id,)).rowcount
        conn.commit()
    return rows > 0


def add_message(conv_id: str, role: str, content: str,
                sources: List[Dict] = None, provider: str = "") -> Dict:
    mid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    sources_json = json.dumps(sources or [])
    with get_db() as conn:
        conn.execute(
            "INSERT INTO messages (id, conversation_id, role, content, sources, provider, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (mid, conv_id, role, content, sources_json, provider, now)
        )
        conn.execute(
            "UPDATE conversations SET updated_at=?, message_count=message_count+1 WHERE id=?",
            (now, conv_id)
        )
        conn.commit()
    return {"id": mid, "conversation_id": conv_id, "role": role,
            "content": content, "sources": sources or [], "provider": provider, "created_at": now}


def get_messages(conv_id: str, limit: Optional[int] = None) -> List[Dict]:
    with get_db() as conn:
        if limit is not None:
            # Truy vấn SQL con để lấy limit tin nhắn mới nhất,
            # sau đó sắp xếp theo thời gian tăng dần (ASC) để mạch hội thoại đúng trình tự.
            # Dùng rowid làm tie-breaker ổn định khi timestamps giống nhau.
            query = """
                SELECT * FROM (
                    SELECT *, rowid AS msg_rowid FROM messages 
                    WHERE conversation_id = ? 
                    ORDER BY created_at DESC, rowid DESC 
                    LIMIT ?
                ) ORDER BY created_at ASC, msg_rowid ASC
            """
            rows = conn.execute(query, (conv_id, limit)).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM messages WHERE conversation_id=? ORDER BY created_at ASC, rowid ASC",
                (conv_id,)
            ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["sources"] = json.loads(d.get("sources", "[]"))
        result.append(d)
    return result


def update_conversation_title(conv_id: str, title: str):
    with get_db() as conn:
        conn.execute("UPDATE conversations SET title=? WHERE id=?", (title, conv_id))
        conn.commit()


def clear_all_conversations() -> bool:
    with get_db() as conn:
        conn.execute("DELETE FROM messages")
        conn.execute("DELETE FROM conversations")
        conn.commit()
    return True
