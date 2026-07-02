"""Admin users listing tests."""

from __future__ import annotations

import asyncio
import sqlite3
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from quiz_bot.config import AppSettings
from quiz_bot.config.constants import CB_ADMIN_USERS, CB_ADMIN_USERS_PAGE_PREFIX
from quiz_bot.config.settings import DEFAULT_ABOUT_US_TEXT
from quiz_bot.database import (
    complete_onboarding_db,
    configure_database_settings,
    init_database,
    list_user_progress_rows_db,
    save_onboarding_age_db,
    save_onboarding_name_db,
    upsert_user_db,
)
from quiz_bot.database.connection import connect
from quiz_bot.handlers import admin_handlers
from quiz_bot.keyboards import admin_dashboard_keyboard


class AdminUsersTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
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
            about_us_text=DEFAULT_ABOUT_US_TEXT,
        )
        configure_database_settings(self._settings)
        init_database(self._settings)
        self.conn = connect(self._settings)

    def tearDown(self) -> None:
        self.conn.close()
        self._tmp.cleanup()

    def test_dashboard_contains_users_button(self) -> None:
        keyboard = admin_dashboard_keyboard("en")
        callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
        self.assertIn(CB_ADMIN_USERS, callbacks)

    def test_empty_user_list_repository(self) -> None:
        self.assertEqual(list_user_progress_rows_db(self.conn), [])

    def test_single_user_includes_profile_fields(self) -> None:
        upsert_user_db(self.conn, 1, "alice", "Telegram Alice", "en")
        save_onboarding_name_db(self.conn, 1, "Alice", "Smith")
        save_onboarding_age_db(self.conn, 1, 22)
        complete_onboarding_db(self.conn, 1, "Tashkent")
        self.conn.commit()

        rows = list_user_progress_rows_db(self.conn)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["user_id"], 1)
        self.assertEqual(rows[0]["username"], "alice")
        self.assertEqual(rows[0]["full_name"], "Alice Smith")
        self.assertEqual(rows[0]["first_name"], "Alice")
        self.assertEqual(rows[0]["last_name"], "Smith")
        self.assertEqual(rows[0]["age"], 22)
        self.assertEqual(rows[0]["region"], "Tashkent")
        self.assertEqual(rows[0]["language_code"], "en")
        self.assertEqual(rows[0]["onboarding_completed"], 1)
        self.assertEqual(rows[0]["score"], 0)
        self.assertIsNotNone(rows[0]["start_time"])

    def test_multiple_users_order_by_id(self) -> None:
        upsert_user_db(self.conn, 3, "carol", "Carol")
        upsert_user_db(self.conn, 1, "alice", "Alice")
        upsert_user_db(self.conn, 2, "bob", "Bob")
        self.conn.commit()

        rows = list_user_progress_rows_db(self.conn)

        self.assertEqual([int(row["user_id"]) for row in rows], [1, 2, 3])

    def test_user_list_pagination(self) -> None:
        for user_id in range(1, 8):
            upsert_user_db(self.conn, user_id, f"user{user_id}", f"User {user_id}")
        self.conn.commit()

        page_two = list_user_progress_rows_db(self.conn, limit=5, offset=5)

        self.assertEqual([int(row["user_id"]) for row in page_two], [6, 7])


    def test_admin_callback_handles_empty_user_list(self) -> None:
        self.conn.execute("INSERT INTO admins (user_id) VALUES (1)")
        self.conn.commit()

        class FakeQuery:
            data = CB_ADMIN_USERS
            message = SimpleNamespace(chat_id=1)

            async def answer(self) -> None:
                return None

            async def edit_message_text(self, text, **kwargs):
                self.text = text
                self.kwargs = kwargs

        async def fake_adb_run(fn, **kwargs):
            return fn(self.conn)

        update = SimpleNamespace(
            callback_query=FakeQuery(),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace(user_data={}, bot=SimpleNamespace())

        with mock.patch.object(admin_handlers, "adb_run", fake_adb_run):
            result = asyncio.run(admin_handlers.admin_callback_router(update, context))

        self.assertEqual(result, -1)
        self.assertEqual(update.callback_query.text, "No users have started the bot yet.")
        callbacks = [
            button.callback_data
            for row in update.callback_query.kwargs["reply_markup"].inline_keyboard
            for button in row
        ]
        self.assertIn(CB_ADMIN_USERS, callbacks)

    def test_admin_callback_denies_non_admin_users(self) -> None:
        class FakeQuery:
            data = CB_ADMIN_USERS
            message = SimpleNamespace(chat_id=1)

            async def answer(self) -> None:
                return None

            async def edit_message_text(self, text, **kwargs):
                self.text = text
                self.kwargs = kwargs

        async def fake_adb_run(fn, **kwargs):
            return False

        update = SimpleNamespace(
            callback_query=FakeQuery(),
            effective_user=SimpleNamespace(id=999),
        )
        context = SimpleNamespace(user_data={}, bot=SimpleNamespace())

        with mock.patch.object(admin_handlers, "adb_run", fake_adb_run):
            result = asyncio.run(admin_handlers.admin_callback_router(update, context))

        self.assertEqual(result, -1)
        self.assertEqual(update.callback_query.text, "Permission denied. You are not an administrator.")

    def test_admin_callback_renders_paginated_users(self) -> None:
        for user_id in range(1, 7):
            upsert_user_db(self.conn, user_id, f"user{user_id}", f"User {user_id}", "en")
        self.conn.execute("INSERT INTO admins (user_id) VALUES (1)")
        self.conn.commit()

        class FakeQuery:
            data = f"{CB_ADMIN_USERS_PAGE_PREFIX}2"
            message = SimpleNamespace(chat_id=1)

            async def answer(self) -> None:
                return None

            async def edit_message_text(self, text, **kwargs):
                self.text = text
                self.kwargs = kwargs

        async def fake_adb_run(fn, **kwargs):
            return fn(self.conn)

        update = SimpleNamespace(
            callback_query=FakeQuery(),
            effective_user=SimpleNamespace(id=1),
        )
        context = SimpleNamespace(user_data={}, bot=SimpleNamespace())

        with mock.patch.object(admin_handlers, "adb_run", fake_adb_run):
            result = asyncio.run(admin_handlers.admin_callback_router(update, context))

        self.assertEqual(result, -1)
        self.assertIn("Users (6) — page 2/2", update.callback_query.text)
        self.assertIn("#6 @user6 (@user6)", update.callback_query.text)
        self.assertEqual(update.callback_query.kwargs["parse_mode"], "Markdown")


if __name__ == "__main__":
    unittest.main()
