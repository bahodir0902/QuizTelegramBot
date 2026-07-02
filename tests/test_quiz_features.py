"""Feature-level tests for onboarding and quiz delivery."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from telegram.constants import PollLimit

from quiz_bot.config import AppSettings
from quiz_bot.config.settings import DEFAULT_ABOUT_US_TEXT
from quiz_bot.database import (
    configure_database_settings,
    get_user_progress_db,
    init_database,
    insert_question_db,
    save_quiz_pool_db,
    upsert_user_db,
)
from quiz_bot.database.connection import connect
from quiz_bot.services.onboarding_service import (
    format_duration,
    parse_age,
    parse_full_name,
    parse_region,
)
from quiz_bot.services.question_service import format_numbered_question
from quiz_bot.services.quiz_progress import continue_quiz_or_finish
from quiz_bot.services.quiz_service import serve_question


class FakeBot:
    def __init__(self) -> None:
        self.messages: list[dict] = []
        self.polls: list[dict] = []

    async def send_message(self, **kwargs):
        self.messages.append(kwargs)
        return SimpleNamespace()

    async def send_poll(self, **kwargs):
        self.polls.append(kwargs)
        return SimpleNamespace(poll=SimpleNamespace(id=f"poll-{len(self.polls)}"))


class FakeContext:
    def __init__(self) -> None:
        self.bot = FakeBot()
        self.application = SimpleNamespace(bot_data={})


class OnboardingServiceTests(unittest.TestCase):
    def test_parse_full_name_requires_first_and_last(self) -> None:
        self.assertEqual(parse_full_name(" Alice   Smith "), ("Alice", "Smith"))
        self.assertEqual(parse_full_name("Alice B Smith"), ("Alice", "B Smith"))
        self.assertIsNone(parse_full_name("Alice"))
        self.assertIsNone(parse_full_name(""))

    def test_parse_age_accepts_only_realistic_decimal_numbers(self) -> None:
        self.assertEqual(parse_age("18"), 18)
        self.assertIsNone(parse_age("18.5"))
        self.assertIsNone(parse_age("-1"))
        self.assertIsNone(parse_age("0"))
        self.assertIsNone(parse_age("121"))
        self.assertIsNone(parse_age("eighteen"))

    def test_parse_region_normalizes_whitespace(self) -> None:
        self.assertEqual(parse_region("  Tashkent   City "), "Tashkent City")
        self.assertIsNone(parse_region("   "))

    def test_format_duration_handles_boundaries(self) -> None:
        self.assertEqual(format_duration(0), "0 seconds")
        self.assertEqual(format_duration(1), "1 second")
        self.assertEqual(format_duration(65), "65 seconds")
        self.assertEqual(format_duration(-5), "0 seconds")


class QuestionFormattingTests(unittest.TestCase):
    def test_question_numbering_includes_index_and_total(self) -> None:
        self.assertEqual(
            format_numbered_question("What is 2+2?", 0, 10),
            "Question 1/10: What is 2+2?",
        )

    def test_question_numbering_respects_telegram_poll_limit(self) -> None:
        text = "x" * 1000
        formatted = format_numbered_question(text, 9, 10)
        self.assertLessEqual(len(formatted), int(PollLimit.MAX_QUESTION_LENGTH))
        self.assertTrue(formatted.startswith("Question 10/10: "))
        self.assertTrue(formatted.endswith("..."))


class QuizDeliveryTests(unittest.IsolatedAsyncioTestCase):
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

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _seed_user_with_pool(self, user_id: int, pool: list[int]) -> None:
        conn = connect(self._settings)
        try:
            upsert_user_db(conn, user_id, "tester", "Test User", "en")
            save_quiz_pool_db(conn, user_id, pool)
            conn.commit()
        finally:
            conn.close()

    async def test_serve_question_numbers_and_protects_poll_content(self) -> None:
        conn = connect(self._settings)
        try:
            upsert_user_db(conn, 100, "tester", "Test User", "en")
            insert_question_db(conn, "2+2?", ["3", "4"], 1)
            save_quiz_pool_db(conn, 100, [1])
            conn.commit()
        finally:
            conn.close()

        context = FakeContext()
        await serve_question(context, user_id=100, chat_id=100)

        self.assertEqual(len(context.bot.polls), 1)
        poll = context.bot.polls[0]
        self.assertEqual(poll["question"], "Question 1/1: 2+2?")
        self.assertTrue(poll["protect_content"])

    async def test_continue_quiz_completion_sends_timed_result(self) -> None:
        self._seed_user_with_pool(101, [1])
        conn = connect(self._settings)
        try:
            conn.execute(
                """
                UPDATE user_progress
                SET current_pool_index = 1,
                    score = 1,
                    start_time = '2026-01-01T00:00:00+00:00'
                WHERE user_id = 101
                """
            )
            conn.commit()
            updated = get_user_progress_db(conn, 101)
        finally:
            conn.close()

        assert updated is not None
        context = FakeContext()
        await continue_quiz_or_finish(context, updated, chat_id=101)

        self.assertEqual(len(context.bot.messages), 1)
        result_text = context.bot.messages[0]["text"]
        self.assertIn("Quiz complete!", result_text)
        self.assertIn("Your score: *1* / 1", result_text)
        self.assertIn("Time taken:", result_text)

        conn = connect(self._settings)
        try:
            row = get_user_progress_db(conn, 101)
        finally:
            conn.close()

        assert row is not None
        self.assertEqual(row["session_status"], "completed")
        self.assertIsNotNone(row["finished_time"])
        self.assertIsNotNone(row["last_duration_seconds"])

class FakeMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.replies: list[dict] = []

    async def reply_text(self, text, **kwargs):
        self.replies.append({"text": text, **kwargs})
        return SimpleNamespace()


class AboutBotHandlerTests(unittest.IsolatedAsyncioTestCase):
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

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _update(self, user_id: int, text: str = ""):
        return SimpleNamespace(
            effective_user=SimpleNamespace(id=user_id, username="tester", full_name="Test User"),
            effective_chat=SimpleNamespace(id=user_id),
            message=FakeMessage(text),
        )

    def _complete_user(self, user_id: int, language: str) -> None:
        conn = connect(self._settings)
        try:
            upsert_user_db(conn, user_id, "tester", "Test User", language)
            conn.execute(
                "UPDATE user_progress SET onboarding_completed = 1 WHERE user_id = ?",
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()

    async def test_about_bot_handler_uses_user_language_text(self) -> None:
        from quiz_bot.database import update_about_bot_text_db
        from quiz_bot.handlers.user_handlers import handle_about_us

        self._complete_user(201, "uz")
        conn = connect(self._settings)
        try:
            update_about_bot_text_db(conn, "uz", "Maxsus uz matn")
            conn.commit()
        finally:
            conn.close()

        update = self._update(201, "ℹ️ Bot haqida")
        await handle_about_us(update, SimpleNamespace())

        self.assertEqual(update.message.replies[0]["text"], "Maxsus uz matn")

    async def test_admin_can_edit_about_bot_text(self) -> None:
        from quiz_bot.database import get_about_bot_text_db, seed_admin_db
        from quiz_bot.handlers.admin_handlers import admin_edit_about_text

        self._complete_user(202, "en")
        conn = connect(self._settings)
        try:
            seed_admin_db(conn, 202)
            conn.commit()
        finally:
            conn.close()

        context = SimpleNamespace(user_data={"edit_about_language": "en"})
        update = self._update(202, "Updated about text")
        result = await admin_edit_about_text(update, context)

        self.assertEqual(result, -1)
        conn = connect(self._settings)
        try:
            self.assertEqual(get_about_bot_text_db(conn, "en"), "Updated about text")
        finally:
            conn.close()
        self.assertIn("updated", update.message.replies[0]["text"].lower())

    async def test_non_admin_cannot_edit_about_bot_text(self) -> None:
        from quiz_bot.database import get_about_bot_text_db
        from quiz_bot.handlers.admin_handlers import admin_edit_about_text

        self._complete_user(203, "en")
        context = SimpleNamespace(user_data={"edit_about_language": "en"})
        update = self._update(203, "Should not save")
        await admin_edit_about_text(update, context)

        conn = connect(self._settings)
        try:
            self.assertNotEqual(get_about_bot_text_db(conn, "en"), "Should not save")
        finally:
            conn.close()
        self.assertIn("Permission denied", update.message.replies[0]["text"])

    async def test_admin_edit_about_bot_rejects_empty_text(self) -> None:
        from quiz_bot.config import ASK_EDIT_ABOUT_TEXT
        from quiz_bot.database import seed_admin_db
        from quiz_bot.handlers.admin_handlers import admin_edit_about_text

        self._complete_user(204, "en")
        conn = connect(self._settings)
        try:
            seed_admin_db(conn, 204)
            conn.commit()
        finally:
            conn.close()

        context = SimpleNamespace(user_data={"edit_about_language": "en"})
        update = self._update(204, "   ")
        result = await admin_edit_about_text(update, context)

        self.assertEqual(result, ASK_EDIT_ABOUT_TEXT)
        self.assertIn("cannot be empty", update.message.replies[0]["text"])


if __name__ == "__main__":
    unittest.main()
