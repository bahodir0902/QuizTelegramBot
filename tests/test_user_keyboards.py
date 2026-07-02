"""User main menu keyboard tests."""

from __future__ import annotations

import unittest

from quiz_bot.keyboards import main_reply_keyboard


def _button_texts(language_code: str, *, is_admin: bool = False) -> list[str]:
    keyboard = main_reply_keyboard(language_code, is_admin=is_admin)
    return [button.text for row in keyboard.keyboard for button in row]


class UserKeyboardTests(unittest.TestCase):
    def test_normal_user_menu_does_not_expose_admin_dashboard(self) -> None:
        texts = _button_texts("en")

        self.assertEqual(
            texts,
            [
                "📝 Tests",
                "📊 My attempts",
                "👤 My information",
                "📡 Channels",
                "ℹ️ About bot",
            ],
        )
        self.assertNotIn("Admin Dashboard", texts)

    def test_admin_menu_includes_admin_dashboard(self) -> None:
        texts = _button_texts("en", is_admin=True)

        self.assertIn("Admin Dashboard", texts)
        self.assertEqual(texts[-1], "Admin Dashboard")

    def test_language_specific_user_menu_labels(self) -> None:
        self.assertEqual(
            _button_texts("uz")[:5],
            [
                "📝 Testlar",
                "📊 Urinishlarim",
                "👤 Mening maʼlumotlarim",
                "📡 Kanallar",
                "ℹ️ Bot haqida",
            ],
        )
        self.assertEqual(
            _button_texts("ru")[:5],
            [
                "📝 Тесты",
                "📊 Мои попытки",
                "👤 Мои данные",
                "📡 Каналы",
                "ℹ️ О боте",
            ],
        )


if __name__ == "__main__":
    unittest.main()
