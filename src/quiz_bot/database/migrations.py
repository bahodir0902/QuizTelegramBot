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
            question_ids_json TEXT,
            current_pool_index INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            current_poll_id TEXT,
            current_correct_index INTEGER,
            current_question_id INTEGER,
            current_option_order_json TEXT,
            session_status TEXT NOT NULL DEFAULT 'idle',
            start_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS admins (
            user_id INTEGER PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS question_answers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            poll_id TEXT NOT NULL UNIQUE,
            selected_option_index INTEGER,
            was_correct INTEGER NOT NULL DEFAULT 0,
            timed_out INTEGER NOT NULL DEFAULT 0,
            answered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(question_id) REFERENCES questions(id) ON DELETE CASCADE
        );
        """
    )

    columns = _column_names(conn, "user_progress")
    if "language_code" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN language_code TEXT")
    if "session_status" not in columns:
        conn.execute(
            "ALTER TABLE user_progress ADD COLUMN session_status TEXT NOT NULL DEFAULT 'idle'"
        )
    if "current_question_id" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN current_question_id INTEGER")
    if "current_option_order_json" not in columns:
        conn.execute("ALTER TABLE user_progress ADD COLUMN current_option_order_json TEXT")

    count = conn.execute("SELECT COUNT(*) FROM configs").fetchone()[0]
    if int(count) == 0:
        conn.execute(
            """
            INSERT INTO configs (
                id, num_questions, shuffle_questions, shuffle_options, question_timeout
            ) VALUES (1, 10, 1, 1, 0)
            """
        )
