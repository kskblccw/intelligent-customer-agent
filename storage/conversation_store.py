"""
会话持久化存储 — SQLite 单文件，零部署。

企业级简化版：
- conversations 表：会话元数据
- messages 表：消息记录，含 answer/thinking_html 等扩展字段
- 按 session_id 隔离，支持多会话切换
"""

import sqlite3
import os
import json
from datetime import datetime, timezone
from utils.pyth_tool import get_abs_path

DB_PATH = get_abs_path("storage/conversations.db")


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    """首次运行时建表"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL DEFAULT '',
            answer TEXT,
            thinking_html TEXT,
            created_at TEXT NOT NULL,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_messages_conv
            ON messages(conversation_id, id);
    """)
    conn.commit()
    conn.close()


# ── 会话操作 ──

def create_conversation(title: str = "") -> str:
    conv_id = datetime.now().strftime("%Y%m%d%H%M%S")
    conn = _get_conn()
    conn.execute(
        "INSERT INTO conversations (id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        (conv_id, title, _now(), _now()),
    )
    conn.commit()
    conn.close()
    return conv_id


def list_conversations(limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations ORDER BY updated_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_conversation(conv_id: str):
    conn = _get_conn()
    conn.execute("DELETE FROM conversations WHERE id = ?", (conv_id,))
    conn.commit()
    conn.close()


def update_conversation_title(conv_id: str, title: str):
    conn = _get_conn()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ?",
        (title, _now(), conv_id),
    )
    conn.commit()
    conn.close()


# ── 消息操作 ──

def save_message(conv_id: str, role: str, content: str,
                 answer: str | None = None, thinking_html: str | None = None):
    conn = _get_conn()
    conn.execute(
        "INSERT INTO messages (conversation_id, role, content, answer, thinking_html, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (conv_id, role, content, answer, thinking_html, _now()),
    )
    conn.execute(
        "UPDATE conversations SET updated_at = ? WHERE id = ?",
        (_now(), conv_id),
    )
    conn.commit()
    conn.close()


def load_messages(conv_id: str) -> list[dict]:
    """按时间顺序加载会话的所有消息"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, answer, thinking_html FROM messages "
        "WHERE conversation_id = ? ORDER BY id ASC",
        (conv_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_recent_messages(conv_id: str, limit: int = 30) -> list[dict]:
    """加载最近 N 条消息（供 Agent 上下文窗口用）"""
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content FROM messages "
        "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conv_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# 启动初始化
init_db()
