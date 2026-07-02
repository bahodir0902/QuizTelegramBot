"""User attempts rendering tests."""

from __future__ import annotations

import sqlite3
import unittest

from quiz_bot.handlers.user_handlers import format_attempts_messages


def _row(**values):
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    columns = ", ".join(values)
    placeholders = ", ".join("?" for _ in values)
    conn.execute(f"CREATE TABLE attempt ({columns})")
    conn.execute(f"INSERT INTO attempt VALUES ({placeholders})", tuple(values.values()))
    return conn.execute("SELECT * FROM attempt").fetchone()


class UserAttemptsRenderingTests(unittest.TestCase):
    def test_empty_history_message_is_localized(self) -> None:
        self.assertEqual(format_attempts_messages([], "en"), ["No attempts yet."])

    def test_correct_incorrect_timeout_and_pagination_render(self) -> None:
        rows = [
            _row(
                answered_at="2026-01-01T00:00:03+00:00",
                timed_out=0,
                was_correct=1,
                options_json='["A", "B"]',
                selected_option_index=1,
                correct_option_index=1,
                question_text="Correct?",
            ),
            _row(
                answered_at="2026-01-01T00:00:02+00:00",
                timed_out=0,
                was_correct=0,
                options_json='["A", "B"]',
                selected_option_index=0,
                correct_option_index=1,
                question_text="Incorrect?",
            ),
            _row(
                answered_at="2026-01-01T00:00:01+00:00",
                timed_out=1,
                was_correct=0,
                options_json='["A", "B"]',
                selected_option_index=None,
                correct_option_index=0,
                question_text="Timeout?",
            ),
        ]

        messages = format_attempts_messages(rows, "en", page_size=2)

        self.assertEqual(len(messages), 2)
        self.assertIn("My attempts (page 1/2)", messages[0])
        self.assertIn("Correct", messages[0])
        self.assertIn("Incorrect", messages[0])
        self.assertIn("Selected answer: 1. B", messages[0])
        self.assertIn("Correct answer: 1. B", messages[0])
        self.assertIn("My attempts (page 2/2)", messages[1])
        self.assertIn("Timed out", messages[1])
        self.assertIn("Selected answer: Not answered", messages[1])


if __name__ == "__main__":
    unittest.main()
