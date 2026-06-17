"""Admin keyboard tests."""

from __future__ import annotations

import sqlite3
import unittest

from quiz_bot.config.constants import (
    CB_ADMIN_QUESTIONS,
    CB_QUESTION_DELETE_OPTION_PREFIX,
    CB_QUESTION_VIEW_PREFIX,
)
from quiz_bot.keyboards import (
    admin_dashboard_keyboard,
    admin_question_options_keyboard,
    admin_questions_keyboard,
)


class AdminKeyboardTests(unittest.TestCase):
    def test_dashboard_contains_manage_questions_button(self) -> None:
        keyboard = admin_dashboard_keyboard("en")
        callback_data = [
            button.callback_data
            for row in keyboard.inline_keyboard
            for button in row
        ]
        self.assertIn(CB_ADMIN_QUESTIONS, callback_data)

    def test_question_list_uses_short_view_callbacks(self) -> None:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE questions (id INTEGER, question_text TEXT, correct_option_index INTEGER)"
        )
        conn.execute(
            "INSERT INTO questions VALUES (123, 'A very long question title that should be shortened', 0)"
        )
        row = conn.execute("SELECT * FROM questions").fetchone()
        assert row is not None
        keyboard = admin_questions_keyboard([row], "en")
        button = keyboard.inline_keyboard[0][0]

        self.assertEqual(button.callback_data, f"{CB_QUESTION_VIEW_PREFIX}123")
        self.assertLessEqual(len(button.callback_data or ""), 64)

    def test_option_delete_callbacks_include_question_and_option_ids(self) -> None:
        keyboard = admin_question_options_keyboard(5, ["A", "B", "C"], "en")
        button = keyboard.inline_keyboard[2][0]

        self.assertEqual(button.callback_data, f"{CB_QUESTION_DELETE_OPTION_PREFIX}5:2")
        self.assertLessEqual(len(button.callback_data or ""), 64)


if __name__ == "__main__":
    unittest.main()
