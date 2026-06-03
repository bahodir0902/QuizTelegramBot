"""Language picker keyboard."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup


def language_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🇺🇸 English", callback_data="lang:en")],
            [InlineKeyboardButton("🇷🇺 Русский", callback_data="lang:ru")],
            [InlineKeyboardButton("🇺🇿 O'zbek", callback_data="lang:uz")],
        ]
    )
