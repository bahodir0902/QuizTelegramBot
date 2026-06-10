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


if __name__ == "__main__":
    unittest.main()
