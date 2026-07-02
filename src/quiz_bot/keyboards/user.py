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

def _menu_label(language_code: str, key: str) -> str:
    labels = {
        "en": {"start": "📝 Tests", "channels": "📡 Channels", "about": "ℹ️ About bot"},
        "ru": {"start": "📝 Тесты", "channels": "📡 Каналы", "about": "ℹ️ О боте"},
        "uz": {"start": "📝 Testlar", "channels": "📡 Kanallar", "about": "ℹ️ Bot haqida"},
    }
    return labels.get(language_code, labels["en"])[key]


def main_reply_keyboard(language_code: str, *, is_admin: bool = False) -> ReplyKeyboardMarkup:
    """Build the localized main menu for a regular user or administrator."""
    rows = [
        [KeyboardButton(_menu_label(language_code, "start"))],
        [KeyboardButton(translate(language_code, "my_attempts_label"))],
        [KeyboardButton(translate(language_code, "my_profile_label"))],
        [KeyboardButton(_menu_label(language_code, "channels"))],
        [KeyboardButton(_menu_label(language_code, "about"))],
    ]
    if is_admin:
        rows.append([KeyboardButton(translate(language_code, "admin_dashboard"))])
    return ReplyKeyboardMarkup(
        rows,
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
