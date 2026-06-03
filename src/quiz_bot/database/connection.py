"""SQLite connection factory."""

from __future__ import annotations

import sqlite3

from quiz_bot.config import AppSettings


def connect(settings: AppSettings) -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, timeout=settings.db_busy_timeout_ms / 1000.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute(f"PRAGMA busy_timeout = {settings.db_busy_timeout_ms}")
    return conn
