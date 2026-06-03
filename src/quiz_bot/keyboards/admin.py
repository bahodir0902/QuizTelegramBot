"""Admin keyboard builders."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from quiz_bot.config.constants import (
    CB_ADMIN_ADD,
    CB_ADMIN_BACK,
    CB_ADMIN_EXPORT,
    CB_ADMIN_SETTINGS,
    CB_ADMIN_STATS,
    CB_SET_LIMIT,
    CB_SET_TIMER,
    CB_TOGGLE_OPT_SHUFFLE,
    CB_TOGGLE_Q_SHUFFLE,
)
from quiz_bot.domain import BotConfig
from quiz_bot.services.localization_service import translate


def admin_dashboard_keyboard(language_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_add_question"),
                    callback_data=CB_ADMIN_ADD,
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "settings"),
                    callback_data=CB_ADMIN_SETTINGS,
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_view_stats"),
                    callback_data=CB_ADMIN_STATS,
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_export_data"),
                    callback_data=CB_ADMIN_EXPORT,
                )
            ],
        ]
    )


def admin_settings_keyboard(config: BotConfig, language_code: str) -> InlineKeyboardMarkup:
    q_state = translate(
        language_code,
        "admin_on" if config.shuffle_questions else "admin_off",
    )
    o_state = translate(
        language_code,
        "admin_on" if config.shuffle_options else "admin_off",
    )
    timer_value = (
        translate(language_code, "admin_timer_disabled")
        if config.question_timeout <= 0
        else f"{config.question_timeout}s"
    )
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_question_limit", count=config.num_questions),
                    callback_data=CB_SET_LIMIT,
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_shuffle_questions", state=q_state),
                    callback_data=CB_TOGGLE_Q_SHUFFLE,
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_shuffle_options", state=o_state),
                    callback_data=CB_TOGGLE_OPT_SHUFFLE,
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_timer", value=timer_value),
                    callback_data=CB_SET_TIMER,
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_back"),
                    callback_data=CB_ADMIN_BACK,
                )
            ],
        ]
    )
