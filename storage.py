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


def init_db() -> None:
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS keywords (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                keyword    TEXT NOT NULL,
                category   TEXT,                       -- NULL = all categories
                created_at TEXT NOT NULL,
                UNIQUE(keyword, category)
            );

            CREATE TABLE IF NOT EXISTS seen_posts (
                post_id INTEGER PRIMARY KEY,
                seen_at TEXT NOT NULL
            );

            -- Generic key-value store for bot state
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.commit()


# ── Keywords ──────────────────────────────────────────────────────────────────

def add_keyword(keyword: str, category: Optional[str] = None) -> bool:
    """
    Add a (keyword, category) pair. category=None means "watch all categories".
    Returns True on success, False if the pair already exists.
    """
    try:
        with _conn() as conn:
            conn.execute(
                "INSERT INTO keywords (keyword, category, created_at) VALUES (?, ?, ?)",
                (keyword.lower(), category, datetime.utcnow().isoformat()),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def remove_keyword(keyword: str) -> int:
    """
    Remove ALL entries for the given keyword (regardless of category).
    Returns the number of rows deleted.
    """
    with _conn() as conn:
        cursor = conn.execute(
            "DELETE FROM keywords WHERE keyword = ?",
            (keyword.lower(),),
        )
        conn.commit()
        return cursor.rowcount


def list_keywords() -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT keyword, category FROM keywords ORDER BY created_at"
        ).fetchall()
    return [dict(r) for r in rows]


# ── Seen posts ────────────────────────────────────────────────────────────────

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


# ── Settings ──────────────────────────────────────────────────────────────────

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
