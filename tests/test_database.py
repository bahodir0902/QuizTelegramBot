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
    delete_question_db,
    delete_question_option_db,
    fetch_question_db,
    fetch_question_stats_db,
    get_user_progress_db,
    increment_score_and_advance_db,
    init_database,
    insert_question_db,
    list_questions_db,
    read_config,
    replace_question_options_db,
    save_quiz_pool_db,
    score_poll_answer_db,
    start_quiz_session_db,
    toggle_config_field_db,
    update_poll_state_db,
    update_question_correct_index_db,
    update_question_text_db,
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

    def test_management_schema_is_initialized(self) -> None:
        conn = self.open_conn()
        progress_columns = {
            str(row["name"])
            for row in conn.execute("PRAGMA table_info(user_progress)").fetchall()
        }
        self.assertIn("current_question_id", progress_columns)
        self.assertIn("current_option_order_json", progress_columns)

        stats_table = conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'question_answers'"
        ).fetchone()
        self.assertIsNotNone(stats_table)

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

    def test_question_management_lifecycle(self) -> None:
        conn = self.open_conn()
        insert_question_db(conn, "Old text?", ["A", "B", "C"], 1)
        conn.commit()
        question_id = int(list_questions_db(conn)[0]["id"])

        self.assertTrue(update_question_text_db(conn, question_id, "New text?"))
        self.assertTrue(replace_question_options_db(conn, question_id, ["One", "Two", "Three"], 2))
        self.assertTrue(update_question_correct_index_db(conn, question_id, 1))
        deleted_option, status = delete_question_option_db(conn, question_id, 0)
        conn.commit()

        self.assertTrue(deleted_option)
        self.assertEqual(status, "ok")
        row = fetch_question_db(conn, question_id)
        self.assertIsNotNone(row)
        assert row is not None
        self.assertEqual(row["question_text"], "New text?")
        self.assertEqual(row["options_json"], '["Two", "Three"]')
        self.assertEqual(int(row["correct_option_index"]), 0)

        self.assertTrue(delete_question_db(conn, question_id))
        conn.commit()
        self.assertIsNone(fetch_question_db(conn, question_id))

    def test_question_option_delete_keeps_minimum_options(self) -> None:
        conn = self.open_conn()
        insert_question_db(conn, "Pick one", ["A", "B"], 0)
        conn.commit()
        question_id = int(list_questions_db(conn)[0]["id"])

        deleted, status = delete_question_option_db(conn, question_id, 0)
        self.assertFalse(deleted)
        self.assertEqual(status, "minimum_options")

    def test_scoring_records_original_option_stats_for_shuffled_poll(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 101, "alice", "Alice")
        insert_question_db(conn, "Pick B", ["A", "B", "C"], 1)
        question_id = int(list_questions_db(conn)[0]["id"])
        save_quiz_pool_db(conn, 101, [question_id])
        update_poll_state_db(conn, 101, "poll-1", 2, question_id, [2, 0, 1])
        updated, status = score_poll_answer_db(conn, "poll-1", 101, 0)
        conn.commit()

        self.assertEqual(status, "ok")
        assert updated is not None
        self.assertEqual(int(updated["score"]), 0)
        stats = fetch_question_stats_db(conn, question_id)
        self.assertIsNotNone(stats)
        assert stats is not None
        self.assertEqual(stats["attempts"], 1)
        self.assertEqual(stats["answered"], 1)
        self.assertEqual(stats["correct"], 0)
        self.assertEqual(stats["timed_out"], 0)
        self.assertEqual(stats["option_counts"], {2: 1})

    def test_scoring_records_correct_answer_stats(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 102, None, "Bob")
        insert_question_db(conn, "Pick B", ["A", "B", "C"], 1)
        question_id = int(list_questions_db(conn)[0]["id"])
        save_quiz_pool_db(conn, 102, [question_id])
        update_poll_state_db(conn, 102, "poll-2", 1, question_id, [0, 1, 2])
        updated, status = score_poll_answer_db(conn, "poll-2", 102, 1)
        conn.commit()

        self.assertEqual(status, "ok")
        assert updated is not None
        self.assertEqual(int(updated["score"]), 1)
        stats = fetch_question_stats_db(conn, question_id)
        self.assertIsNotNone(stats)
        assert stats is not None
        self.assertEqual(stats["correct"], 1)
        self.assertEqual(stats["option_counts"], {1: 1})

    def test_timeout_records_question_stats(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 103, None, "Eve")
        insert_question_db(conn, "Timed?", ["Yes", "No"], 0)
        question_id = int(list_questions_db(conn)[0]["id"])
        save_quiz_pool_db(conn, 103, [question_id])
        update_poll_state_db(conn, 103, "poll-timeout", 0, question_id, [0, 1])
        updated, status = advance_timeout_poll_db(conn, "poll-timeout", 103)
        conn.commit()

        self.assertEqual(status, "ok")
        assert updated is not None
        stats = fetch_question_stats_db(conn, question_id)
        self.assertIsNotNone(stats)
        assert stats is not None
        self.assertEqual(stats["attempts"], 1)
        self.assertEqual(stats["answered"], 0)
        self.assertEqual(stats["timed_out"], 1)

    def test_answer_after_question_deleted_still_advances_session(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 104, None, "Dana")
        insert_question_db(conn, "Deleted?", ["Yes", "No"], 0)
        question_id = int(list_questions_db(conn)[0]["id"])
        save_quiz_pool_db(conn, 104, [question_id])
        update_poll_state_db(conn, 104, "poll-deleted", 0, question_id, [0, 1])
        delete_question_db(conn, question_id)

        updated, status = score_poll_answer_db(conn, "poll-deleted", 104, 0)
        conn.commit()

        self.assertEqual(status, "ok")
        assert updated is not None
        self.assertEqual(int(updated["score"]), 1)
        self.assertEqual(int(updated["current_pool_index"]), 1)
        rows = conn.execute("SELECT * FROM question_answers").fetchall()
        self.assertEqual(rows, [])

    def test_timeout_after_question_deleted_still_advances_session(self) -> None:
        conn = self.open_conn()
        upsert_user_db(conn, 105, None, "Finn")
        insert_question_db(conn, "Deleted timeout?", ["Yes", "No"], 0)
        question_id = int(list_questions_db(conn)[0]["id"])
        save_quiz_pool_db(conn, 105, [question_id])
        update_poll_state_db(conn, 105, "poll-deleted-timeout", 0, question_id, [0, 1])
        delete_question_db(conn, question_id)

        updated, status = advance_timeout_poll_db(conn, "poll-deleted-timeout", 105)
        conn.commit()

        self.assertEqual(status, "ok")
        assert updated is not None
        self.assertEqual(int(updated["current_pool_index"]), 1)
        rows = conn.execute("SELECT * FROM question_answers").fetchall()
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
