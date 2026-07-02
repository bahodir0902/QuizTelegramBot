"""Admin keyboard tests."""

from __future__ import annotations

import sqlite3
import unittest

from quiz_bot.config.constants import (
    CB_ADMIN_ADD,
    CB_ADMIN_BACK,
    CB_ADMIN_EXPORT,
    CB_ADMIN_QUESTIONS,
    CB_ADMIN_SEND_MESSAGE,
    CB_ADMIN_SETTINGS,
    CB_ADMIN_STATS,
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

    def test_dashboard_layout_for_all_languages(self) -> None:
        expected = {
            "en": [
                [("📣 Send message", CB_ADMIN_SEND_MESSAGE)],
                [("🧩 Create test", CB_ADMIN_ADD), ("📚 Tests", CB_ADMIN_QUESTIONS)],
                [("📊 Results", CB_ADMIN_STATS)],
                [("📡 Channels", CB_ADMIN_SETTINGS), ("👥 Users", CB_ADMIN_EXPORT)],
                [("⬅️ Back", CB_ADMIN_BACK)],
            ],
            "ru": [
                [("📣 Отправить сообщение", CB_ADMIN_SEND_MESSAGE)],
                [("🧩 Создать тест", CB_ADMIN_ADD), ("📚 Тесты", CB_ADMIN_QUESTIONS)],
                [("📊 Результаты", CB_ADMIN_STATS)],
                [("📡 Каналы", CB_ADMIN_SETTINGS), ("👥 Пользователи", CB_ADMIN_EXPORT)],
                [("⬅️ Назад", CB_ADMIN_BACK)],
            ],
            "uz": [
                [("📣 Xabar yuborish", CB_ADMIN_SEND_MESSAGE)],
                [("🧩 Test yaratish", CB_ADMIN_ADD), ("📚 Testlar", CB_ADMIN_QUESTIONS)],
                [("📊 Natijalar", CB_ADMIN_STATS)],
                [("📡 Kanallar", CB_ADMIN_SETTINGS), ("👥 Foydalanuvchilar", CB_ADMIN_EXPORT)],
                [("⬅️ Orqaga", CB_ADMIN_BACK)],
            ],
        }

        for language_code, expected_layout in expected.items():
            with self.subTest(language_code=language_code):
                keyboard = admin_dashboard_keyboard(language_code)
                layout = [
                    [(button.text, button.callback_data) for button in row]
                    for row in keyboard.inline_keyboard
                ]
                self.assertEqual(layout, expected_layout)

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
