"""Schema initialization and migration helpers."""

from __future__ import annotations

import sqlite3


def _column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {str(row[1]) for row in rows}


def apply_migrations(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS configs (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            num_questions INTEGER DEFAULT 10,
            shuffle_questions INTEGER DEFAULT 1,
            shuffle_options INTEGER DEFAULT 1,
            question_timeout INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_text TEXT NOT NULL,
            options_json TEXT NOT NULL,
            correct_option_index INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS user_progress (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            full_name TEXT,
            language_code TEXT,
            first_name TEXT,
            last_name TEXT,
            age INTEGER,
            region TEXT,
            onboarding_completed INTEGER NOT NULL DEFAULT 0,
            onboarding_step TEXT,
            onboarded_at TIMESTAMP,
            question_ids_json TEXT,
            current_pool_index INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            current_poll_id TEXT,
            current_correct_index INTEGER,
            session_status TEXT NOT NULL DEFAULT 'idle',
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            finished_time TIMESTAMP,
            last_duration_seconds INTEGER
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        );
        """
    )

    columns = _column_names(conn, "user_progress")
    if "language_code" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN language_code TEXT")
    if "first_name" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN first_name TEXT")
    if "last_name" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN last_name TEXT")
    if "age" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN age INTEGER")
    if "region" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN region TEXT")
    onboarding_column_existed = "onboarding_completed" in columns
    if "onboarding_completed" not in columns:
        conn.execute(
            "ALTER TABLE user_progress ADD COLUMN onboarding_completed INTEGER NOT NULL DEFAULT 0"
        )
    if "onboarding_step" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN onboarding_step TEXT")
    if "onboarded_at" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN onboarded_at TIMESTAMP")
    if "session_status" not in columns:
        conn.execute(
            "ALTER TABLE user_progress ADD COLUMN session_status TEXT NOT NULL DEFAULT 'idle'"
        )
    if "finished_time" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN finished_time TIMESTAMP")
    if "last_duration_seconds" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN last_duration_seconds INTEGER")

    if not onboarding_column_existed:
        conn.execute(
            """
            UPDATE user_progress
            SET onboarding_completed = 1,
                onboarding_step = NULL
            """
        )

    count = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
    if int(count) == 0:
        conn.execute(
            """
            INSERT INTO configs (
                id, num_questions, shuffle_questions, shuffle_options, question_timeout
            ) VALUES (1, 10, 1, 1, 0)
            """
        )
