"""User keyboard builders."""

from __future__ import annotations

from telegram import KeyboardButton, ReplyKeyboardMarkup

from quiz_bot.services.localization_service import translate


def main_reply_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(translate(language_code, "start_quiz_label"))],
            [KeyboardButton(translate(language_code, "change_language_label"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )
