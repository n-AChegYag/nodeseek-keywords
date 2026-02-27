import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config import DATABASE_PATH


def _conn() -> sqlite3.Connection:
    Path(DATABASE_PATH).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    # Enable WAL for slightly better concurrent read performance
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _migrate(conn: sqlite3.Connection) -> None:
    """Non-destructive schema migration: add new columns to existing tables if absent."""
    kw_cols = {row["name"] for row in conn.execute("PRAGMA table_info(keywords)").fetchall()}
    if "match_mode" not in kw_cols:
        conn.execute(
            "ALTER TABLE keywords ADD COLUMN match_mode TEXT NOT NULL DEFAULT 'substring'"
        )
    if "enabled" not in kw_cols:
        conn.execute(
            "ALTER TABLE keywords ADD COLUMN enabled INTEGER NOT NULL DEFAULT 1"
        )


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS keywords (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword    TEXT NOT NULL,
                category   TEXT,                       -- NULL = all categories
                match_mode TEXT NOT NULL DEFAULT 'substring',
                enabled    INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                UNIQUE(keyword, category)
            );

            CREATE TABLE IF NOT EXISTS seen_posts (
                post_id INTEGER PRIMARY KEY,
                seen_at TEXT NOT NULL
            );

            -- Notification history: one row per (post_id, keyword) match
            CREATE TABLE IF NOT EXISTS notifications (
                id       INTEGER PRIMARY KEY AUTOINCREMENT,
                post_id  INTEGER NOT NULL,
                keyword  TEXT NOT NULL,
                title    TEXT NOT NULL,
                link     TEXT NOT NULL,
                category TEXT NOT NULL,
                author   TEXT NOT NULL,
                status   TEXT NOT NULL DEFAULT 'sent',  -- 'sent' | 'failed'
                sent_at  TEXT NOT NULL
            );

            -- Generic key-value store for bot state
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        _migrate(conn)
        conn.commit()


# ── Keywords ───────────────────────────────────────────────────────────────────

def add_keyword(
    keyword: str,
    category: Optional[str] = None,
    match_mode: str = "substring",
) -> bool:
    """
    Add a (keyword, category) pair. Keyword is stored as-is (original case preserved).
    Duplicate check is case-insensitive. Returns True on success, False if duplicate.
    """
    with _conn() as conn:
        # Case-insensitive duplicate check handles both old (lowercase) and new storage
        existing = conn.execute(
            """SELECT 1 FROM keywords
               WHERE keyword = ? COLLATE NOCASE
               AND (category IS ? OR category = ?)""",
            (keyword, category, category),
        ).fetchone()
        if existing:
            return False
        try:
            conn.execute(
                "INSERT INTO keywords (keyword, category, match_mode, created_at) VALUES (?, ?, ?, ?)",
                (keyword, category, match_mode, datetime.utcnow().isoformat()),
            )
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False


def remove_keyword(keyword: str) -> int:
    """Remove ALL entries for the given keyword (case-insensitive). Returns rows deleted."""
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM keywords WHERE keyword = ? COLLATE NOCASE",
            (keyword,),
        )
        conn.commit()
        return cursor.rowcount


def list_keywords() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT keyword, category, match_mode, enabled FROM keywords ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


def set_keyword_enabled(keyword: str, enabled: bool) -> int:
    """Enable or disable all entries for a keyword (case-insensitive). Returns rows affected."""
    with _conn() as conn:
        cursor = conn.execute(
            "UPDATE keywords SET enabled = ? WHERE keyword = ? COLLATE NOCASE",
            (1 if enabled else 0, keyword),
        )
        conn.commit()
        return cursor.rowcount


# ── Seen posts ─────────────────────────────────────────────────────────────────

def is_seen(post_id: int) -> bool:
    with _conn() as conn:
        return (
            conn.execute(
                "SELECT 1 FROM seen_posts WHERE post_id = ?", (post_id,)
            ).fetchone()
            is not None
        )


def mark_seen(post_id: int) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO seen_posts (post_id, seen_at) VALUES (?, ?)",
            (post_id, datetime.utcnow().isoformat()),
        )
        conn.commit()


def mark_many_seen(post_ids: list[int]) -> None:
    now = datetime.utcnow().isoformat()
    with _conn() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO seen_posts (post_id, seen_at) VALUES (?, ?)",
            [(pid, now) for pid in post_ids],
        )
        conn.commit()


def cleanup_old_seen(keep_days: int = 7) -> None:
    """Prune old seen_posts rows to keep the DB from growing unbounded."""
    cutoff = (datetime.utcnow() - timedelta(days=keep_days)).isoformat()
    with _conn() as conn:
        conn.execute("DELETE FROM seen_posts WHERE seen_at < ?", (cutoff,))
        conn.commit()


# ── Notifications ──────────────────────────────────────────────────────────────

def log_notification(
    post_id: int,
    keyword: str,
    title: str,
    link: str,
    category: str,
    author: str,
    status: str = "sent",
) -> None:
    with _conn() as conn:
        conn.execute(
            """INSERT INTO notifications
               (post_id, keyword, title, link, category, author, status, sent_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (post_id, keyword, title, link, category, author, status,
             datetime.utcnow().isoformat()),
        )
        conn.commit()


def get_history(limit: int = 10) -> list[dict]:
    """
    Return the last `limit` distinct posts that triggered notifications, newest first.
    Keywords are comma-joined when multiple keywords matched the same post.
    Status is 'failed' if any keyword notification for the post failed.
    """
    with _conn() as conn:
        rows = conn.execute(
            """SELECT post_id,
                      GROUP_CONCAT(DISTINCT keyword) AS keywords,
                      title, link, category, author,
                      MIN(status)      AS status,
                      MAX(sent_at)     AS sent_at
               FROM notifications
               GROUP BY post_id
               ORDER BY sent_at DESC
               LIMIT ?""",
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


def cleanup_old_notifications(keep_days: int = 30) -> None:
    """Prune old notification rows to keep the DB from growing unbounded."""
    cutoff = (datetime.utcnow() - timedelta(days=keep_days)).isoformat()
    with _conn() as conn:
        conn.execute("DELETE FROM notifications WHERE sent_at < ?", (cutoff,))
        conn.commit()


# ── Settings ───────────────────────────────────────────────────────────────────

def get_setting(key: str) -> Optional[str]:
    with _conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else None


def set_setting(key: str, value: str) -> None:
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)",
            (key, value),
        )
        conn.commit()
