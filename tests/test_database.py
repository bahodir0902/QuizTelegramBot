"""Database layer tests."""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path

from quiz_bot.config import AppSettings
from quiz_bot.database import (
    BotConfig,
    adb_run,
    advance_timeout_poll_db,
    configure_database_settings,
    get_user_progress_db,
    increment_score_and_advance_db,
    init_database,
    insert_question_db,
    read_config,
    save_quiz_pool_db,
    start_quiz_session_db,
    toggle_config_field_db,
    upsert_user_db,
)
from quiz_bot.database.connection import connect


class DatabaseLayerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self._connections: list[sqlite3.Connection] = []
        self._settings = AppSettings(
            bot_token="TEST_TOKEN",
            initial_admin_ids=tuple(),
            data_dir=Path(self._tmp.name),
            db_path=Path(self._tmp.name) / "test.db",
            log_level="INFO",
            default_language="en",
            db_busy_timeout_ms=5000,
            connect_timeout=10.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=10.0,
        )
        configure_database_settings(self._settings)
        init_database(self._settings)

    def tearDown(self) -> None:
        for conn in self._connections:
            conn.close()
        self._connections.clear()
        self._tmp.cleanup()

    def open_conn(self) -> sqlite3.Connection:
        conn = connect(self._settings)
        self._connections.append(conn)
        return conn

    def test_read_config_defaults(self) -> None:
        conn = self.open_conn()
        config = read_config(conn)
        self.assertEqual(config.num_questions, 10)
        self.assertTrue(config.shuffle_questions)
        self.assertTrue(config.shuffle_options)
        self.assertEqual(config.question_timeout, 0)

    def test_adb_run_accepts_connection_callbacks(self) -> None:
        async def _run() -> BotConfig:
            return await adb_run(read_config)

        config = asyncio.run(_run())
        self.assertIsInstance(config, BotConfig)

    def test_insert_and_start_quiz_session(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 42, "alice", "Alice")
        insert_question_db(conn, "2+2?", ["3", "4"], 1)
        conn.commit()

        conn = self.open_conn()
        pool = start_quiz_session_db(conn, 42)
        conn.commit()
        self.assertEqual(len(pool), 1)

        conn = self.open_conn()
        row = get_user_progress_db(conn, 42)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(int(row["score"]), 0)
        self.assertEqual(int(row["current_pool_index"]), 0)

    def test_toggle_shuffle_questions(self) -> None:
        conn = self.open_conn()
        config = toggle_config_field_db(conn, "shuffle_questions")
        conn.commit()
        self.assertFalse(config.shuffle_questions)

    def test_increment_score_and_advance(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 7, None, "Bob")
        save_quiz_pool_db(conn, 7, [1])
        updated = increment_score_and_advance_db(conn, 7, True)
        conn.commit()
        self.assertEqual(int(updated["score"]), 1)
        self.assertEqual(int(updated["current_pool_index"]), 1)

    def test_advance_timeout_poll_on_last_question(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 9, None, "Eve")
        save_quiz_pool_db(conn, 9, [1])
        conn.execute(
            "UPDATE user_progress SET current_poll_id = ?, current_correct_index = ? WHERE user_id = ?",
            ("poll-1", 0, 9),
        )
        conn.commit()

        conn = self.open_conn()
        updated, status = advance_timeout_poll_db(conn, "poll-1", 9)
        conn.commit()
        self.assertEqual(status, "ok")
        assert updated is not None
        self.assertEqual(int(updated["score"]), 0)
        self.assertEqual(int(updated["current_pool_index"]), 1)
        self.assertIsNone(updated["current_poll_id"])


if __name__ == "__main__":
    unittest.main()
