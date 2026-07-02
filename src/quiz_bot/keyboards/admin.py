"""Admin keyboard builders."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from quiz_bot.config.constants import (
    CB_ADMIN_ADD,
    CB_ADMIN_BACK,
    CB_ADMIN_EXPORT,
    CB_ADMIN_QUESTIONS,
    CB_ADMIN_SETTINGS,
    CB_ADMIN_STATS,
    CB_ADMIN_USERS,
    CB_ADMIN_USERS_PAGE_PREFIX,
    CB_QUESTION_DELETE_CONFIRM_PREFIX,
    CB_QUESTION_DELETE_OPTION_PREFIX,
    CB_QUESTION_DELETE_PREFIX,
    CB_QUESTION_EDIT_CORRECT_PREFIX,
    CB_QUESTION_EDIT_OPTIONS_PREFIX,
    CB_QUESTION_EDIT_TEXT_PREFIX,
    CB_QUESTION_OPTIONS_PREFIX,
    CB_QUESTION_VIEW_PREFIX,
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
                    translate(language_code, "admin_manage_questions"),
                    callback_data=CB_ADMIN_QUESTIONS,
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
                    translate(language_code, "admin_users"),
                    callback_data=CB_ADMIN_USERS,
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


def _shorten(text: str, limit: int = 40) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) <= limit:
        return cleaned
    return f"{cleaned[: limit - 1]}..."


def admin_questions_keyboard(rows, language_code: str) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for row in rows:
        question_id = int(row["id"])
        buttons.append(
            [
                InlineKeyboardButton(
                    f"#{question_id} {_shorten(str(row['question_text']))}",
                    callback_data=f"{CB_QUESTION_VIEW_PREFIX}{question_id}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                translate(language_code, "admin_back"),
                callback_data=CB_ADMIN_BACK,
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


def admin_question_detail_keyboard(question_id: int, language_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_edit_question_text"),
                    callback_data=f"{CB_QUESTION_EDIT_TEXT_PREFIX}{question_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_edit_options"),
                    callback_data=f"{CB_QUESTION_EDIT_OPTIONS_PREFIX}{question_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_set_correct_option"),
                    callback_data=f"{CB_QUESTION_EDIT_CORRECT_PREFIX}{question_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_manage_options"),
                    callback_data=f"{CB_QUESTION_OPTIONS_PREFIX}{question_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_delete_question"),
                    callback_data=f"{CB_QUESTION_DELETE_CONFIRM_PREFIX}{question_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_back"),
                    callback_data=CB_ADMIN_QUESTIONS,
                )
            ],
        ]
    )


def admin_question_delete_keyboard(question_id: int, language_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_confirm_delete"),
                    callback_data=f"{CB_QUESTION_DELETE_PREFIX}{question_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    translate(language_code, "admin_cancel_delete"),
                    callback_data=f"{CB_QUESTION_VIEW_PREFIX}{question_id}",
                )
            ],
        ]
    )


def admin_question_options_keyboard(
    question_id: int,
    options: list[str],
    language_code: str,
) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []
    for index, option in enumerate(options):
        buttons.append(
            [
                InlineKeyboardButton(
                    translate(
                        language_code,
                        "admin_delete_option_button",
                        index=index,
                        option=_shorten(option, 28),
                    ),
                    callback_data=f"{CB_QUESTION_DELETE_OPTION_PREFIX}{question_id}:{index}",
                )
            ]
        )
    buttons.append(
        [
            InlineKeyboardButton(
                translate(language_code, "admin_back"),
                callback_data=f"{CB_QUESTION_VIEW_PREFIX}{question_id}",
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)


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


def admin_users_pagination_keyboard(
    language_code: str,
    *,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    nav: list[InlineKeyboardButton] = []
    if page > 1:
        nav.append(
            InlineKeyboardButton(
                translate(language_code, "admin_users_prev"),
                callback_data=f"{CB_ADMIN_USERS_PAGE_PREFIX}{page - 1}",
            )
        )
    if page < total_pages:
        nav.append(
            InlineKeyboardButton(
                translate(language_code, "admin_users_next"),
                callback_data=f"{CB_ADMIN_USERS_PAGE_PREFIX}{page + 1}",
            )
        )

    buttons: list[list[InlineKeyboardButton]] = []
    if nav:
        buttons.append(nav)
    buttons.append(
        [
            InlineKeyboardButton(
                translate(language_code, "admin_back"),
                callback_data=CB_ADMIN_BACK,
            )
        ]
    )
    return InlineKeyboardMarkup(buttons)
