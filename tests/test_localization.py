"""Localization tests."""

from __future__ import annotations

import unittest

from quiz_bot.locales.messages import MESSAGES


class LocalizationTests(unittest.TestCase):
    def test_all_languages_define_the_same_message_keys(self) -> None:
        expected = set(MESSAGES["en"])
        for language_code, messages in MESSAGES.items():
            self.assertEqual(
                expected,
                set(messages),
                f"{language_code} message keys differ from English",
            )

    def test_no_message_values_are_blank(self) -> None:
        for language_code, messages in MESSAGES.items():
            for key, value in messages.items():
                with self.subTest(language_code=language_code, key=key):
                    self.assertIsInstance(value, str)
                    self.assertTrue(value.strip(), f"{language_code}.{key} is blank")

    def test_major_user_and_admin_labels_are_localized(self) -> None:
        expected_labels = {
            "en": {
                "start_quiz_label": "Start Quiz",
                "my_info_label": "My Info",
                "about_bot_label": "About Bot",
                "admin_dashboard": "Admin Dashboard",
                "broadcast_label": "Broadcast",
                "users_list_label": "Users List",
                "channels_label": "Channels",
            },
            "ru": {
                "start_quiz_label": "Начать викторину",
                "my_info_label": "Моя информация",
                "about_bot_label": "О боте",
                "admin_dashboard": "Панель администратора",
                "broadcast_label": "Рассылка",
                "users_list_label": "Список пользователей",
                "channels_label": "Каналы",
            },
            "uz": {
                "start_quiz_label": "Testni Boshlash",
                "my_info_label": "Mening maʼlumotlarim",
                "about_bot_label": "Bot haqida",
                "admin_dashboard": "Administrator paneli",
                "broadcast_label": "Xabar tarqatish",
                "users_list_label": "Foydalanuvchilar roʻyxati",
                "channels_label": "Kanallar",
            },
        }

        for language_code, labels in expected_labels.items():
            for key, expected in labels.items():
                with self.subTest(language_code=language_code, key=key):
                    self.assertEqual(expected, MESSAGES[language_code][key])


if __name__ == "__main__":
    unittest.main()
