"""User keyboard builders."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup

from quiz_bot.services.localization_service import translate

REGION_OPTIONS = (
    "Tashkent City",
    "Tashkent Region",
    "Andijan",
    "Bukhara",
    "Fergana",
    "Jizzakh",
    "Karakalpakstan",
    "Kashkadarya",
    "Khorezm",
    "Namangan",
    "Navoi",
    "Samarkand",
    "Sirdarya",
    "Surkhandarya",
)


def main_reply_keyboard(language_code: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton(translate(language_code, "start_quiz_label"))],
            [KeyboardButton(translate(language_code, "about_us_label"))],
            [KeyboardButton(translate(language_code, "channels_label"))],
            [KeyboardButton(translate(language_code, "change_language_label"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
    )


def region_reply_keyboard() -> ReplyKeyboardMarkup:
    rows = [
        [KeyboardButton(region) for region in REGION_OPTIONS[index : index + 2]]
        for index in range(0, len(REGION_OPTIONS), 2)
    ]
    return ReplyKeyboardMarkup(
        rows,
        resize_keyboard=True,
        one_time_keyboard=True,
        input_field_placeholder="Choose or type your region",
    )


def channels_inline_keyboard(channels, language_code: str, include_check: bool = False) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(str(row["title"]), url=str(row["url"]))]
        for row in channels
    ]
    if include_check:
        rows.append([InlineKeyboardButton(translate(language_code, "check_subscription_label"), callback_data="channels:check")])
    return InlineKeyboardMarkup(rows)
