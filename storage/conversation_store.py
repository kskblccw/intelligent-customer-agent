"""
会话持久化存储 — SQLite 单文件，零部署。
多用户隔离：users 表管理登录，conversations 按 user_id 隔离。
"""

import sqlite3
import os
import hashlib
import secrets
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


def _hash_password(password: str, salt: str | None = None) -> tuple[str, str]:
    if salt is None:
        salt = secrets.token_hex(16)
    h = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 100000)
    return h.hex(), salt


def init_db():
    """首次运行时建表并兼容升级"""
    conn = _get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            salt TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL DEFAULT '',
            title TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
    # 兼容旧数据库：如果 conversations 表缺少 user_id 列，自动补充
    cols = {r[1] for r in conn.execute("PRAGMA table_info('conversations')").fetchall()}
    if "user_id" not in cols:
        conn.execute("ALTER TABLE conversations ADD COLUMN user_id TEXT NOT NULL DEFAULT ''")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_conversations_user "
        "ON conversations(user_id, updated_at DESC)"
    )
    conn.commit()
    conn.close()


# ── 用户操作 ──

def register_user(username: str, password: str) -> str | None:
    """注册成功返回 user_id，用户名已存在返回 None"""
    username = username.strip()
    if not username or not password:
        return None
    conn = _get_conn()
    existing = conn.execute(
        "SELECT id FROM users WHERE username = ?", (username,)
    ).fetchone()
    if existing:
        conn.close()
        return None
    pwd_hash, salt = _hash_password(password)
    user_id = f"u{datetime.now().strftime('%Y%m%d%H%M%S')}{secrets.token_hex(3)}"
    conn.execute(
        "INSERT INTO users (id, username, password_hash, salt, created_at) VALUES (?, ?, ?, ?, ?)",
        (user_id, username, pwd_hash, salt, _now()),
    )
    conn.commit()
    conn.close()
    return user_id


def verify_user(username: str, password: str) -> str | None:
    """验证通过返回 user_id，失败返回 None"""
    username = username.strip()
    conn = _get_conn()
    row = conn.execute(
        "SELECT id, password_hash, salt FROM users WHERE username = ?", (username,)
    ).fetchone()
    conn.close()
    if not row:
        return None
    h, _ = _hash_password(password, row["salt"])
    if h == row["password_hash"]:
        return row["id"]
    return None


def reset_password(username: str, new_password: str) -> bool:
    """重置密码，成功返回 True，用户不存在返回 False"""
    username = username.strip()
    if not username or len(new_password) < 4:
        return False
    conn = _get_conn()
    row = conn.execute("SELECT id FROM users WHERE username = ?", (username,)).fetchone()
    if not row:
        conn.close()
        return False
    pwd_hash, salt = _hash_password(new_password)
    conn.execute(
        "UPDATE users SET password_hash = ?, salt = ? WHERE id = ?",
        (pwd_hash, salt, row["id"]),
    )
    conn.commit()
    conn.close()
    return True


# ── 会话操作 ──

def create_conversation(user_id: str, title: str = "") -> str:
    conv_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    conn = _get_conn()
    conn.execute(
        "INSERT INTO conversations (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (conv_id, user_id, title, _now(), _now()),
    )
    conn.commit()
    conn.close()
    return conv_id


def list_conversations(user_id: str, limit: int = 20) -> list[dict]:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, title, created_at, updated_at FROM conversations "
        "WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
        (user_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_conversation(conv_id: str, user_id: str):
    """按 conversation id + user_id 删除，确保用户只能删自己的"""
    conn = _get_conn()
    conn.execute(
        "DELETE FROM conversations WHERE id = ? AND user_id = ?",
        (conv_id, user_id),
    )
    conn.commit()
    conn.close()


def update_conversation_title(conv_id: str, title: str, user_id: str):
    conn = _get_conn()
    conn.execute(
        "UPDATE conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
        (title, _now(), conv_id, user_id),
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
    conn = _get_conn()
    rows = conn.execute(
        "SELECT role, content, answer, thinking_html FROM messages "
        "WHERE conversation_id = ? ORDER BY id ASC",
        (conv_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def load_recent_messages(conv_id: str, limit: int = 30) -> list[dict]:
    conn = _get_conn()
    # assistant 消息优先取干净的 answer（content 含思考过程与工具输出，会污染模型上下文）
    rows = conn.execute(
        "SELECT role, COALESCE(NULLIF(answer, ''), content) AS content FROM messages "
        "WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conv_id, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


# 启动初始化
init_db()
