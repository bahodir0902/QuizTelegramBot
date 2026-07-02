"""Application assembly."""

from __future__ import annotations

import re

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    PollAnswerHandler,
    filters,
)
from telegram.request import HTTPXRequest

from quiz_bot.config import (
    ASK_BROADCAST_CONFIRM,
    ASK_BROADCAST_TEXT,
    ASK_CORRECT_INDEX,
    ASK_EDIT_CORRECT_INDEX,
    ASK_EDIT_OPTIONS,
    ASK_EDIT_QUESTION_TEXT,
    ASK_NUM_QUESTIONS,
    ASK_ONBOARD_AGE,
    ASK_ONBOARD_FULL_NAME,
    ASK_ONBOARD_REGION,
    ASK_OPTIONS,
    ASK_QUESTION_TEXT,
    ASK_TIMER_SECONDS,
    AppSettings,
)
from quiz_bot.handlers.admin_handlers import (
    admin_add_correct_index,
    admin_add_options,
    admin_add_question_text,
    admin_broadcast_confirm,
    admin_broadcast_text,
    admin_callback_router,
    admin_edit_correct_index,
    admin_edit_options,
    admin_edit_question_text,
    admin_set_num_questions,
    admin_set_timer,
    cmd_admin,
)
from quiz_bot.handlers.error_handlers import cmd_cancel, on_error
from quiz_bot.handlers.language_handlers import (
    cmd_language,
    handle_change_language,
    handle_language_callback,
)
from quiz_bot.handlers.poll_handlers import handle_poll_answer
from quiz_bot.handlers.user_handlers import (
    cmd_start,
    handle_about_us,
    handle_onboarding_age,
    handle_onboarding_name,
    handle_onboarding_region,
    handle_start_quiz,
)
from quiz_bot.locales.messages import ABOUT_US_LABELS, CHANGE_LANGUAGE_LABELS, START_QUIZ_LABELS


def _build_request(settings: AppSettings) -> HTTPXRequest:
    return HTTPXRequest(
        read_timeout=settings.read_timeout + 5,
        connect_timeout=settings.connect_timeout,
    )


def _start_quiz_regex() -> str:
    escaped = [re.escape(label) for label in START_QUIZ_LABELS]
    return "^(" + "|".join(escaped) + ")$"


def _change_language_regex() -> str:
    escaped = [re.escape(label) for label in CHANGE_LANGUAGE_LABELS]
    return "^(" + "|".join(escaped) + ")$"


def _about_us_regex() -> str:
    escaped = [re.escape(label) for label in ABOUT_US_LABELS]
    return "^(" + "|".join(escaped) + ")$"


def build_application(settings: AppSettings) -> Application:
    """Build the Telegram application."""
    app = (
        Application.builder()
        .token(settings.bot_token)
        .request(_build_request(settings))
        # .get_updates_read_timeout(settings.read_timeout + 5)
        .build()
    )
    app.bot_data["settings"] = settings

    admin_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(admin_callback_router, pattern="^admin:"),
            CallbackQueryHandler(admin_callback_router, pattern="^settings:"),
            CallbackQueryHandler(admin_callback_router, pattern="^question:"),
            CallbackQueryHandler(admin_broadcast_confirm, pattern="^broadcast:"),
        ],
        states={
            ASK_QUESTION_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_add_question_text,
                )
            ],
            ASK_OPTIONS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_add_options,
                )
            ],
            ASK_CORRECT_INDEX: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_add_correct_index,
                )
            ],
            ASK_NUM_QUESTIONS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_set_num_questions,
                )
            ],
            ASK_TIMER_SECONDS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_set_timer,
                )
            ],
            ASK_EDIT_QUESTION_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_edit_question_text,
                )
            ],
            ASK_EDIT_OPTIONS: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_edit_options,
                )
            ],
            ASK_EDIT_CORRECT_INDEX: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_edit_correct_index,
                )
            ],
            ASK_BROADCAST_TEXT: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    admin_broadcast_text,
                )
            ],
            ASK_BROADCAST_CONFIRM: [
                CallbackQueryHandler(admin_broadcast_confirm, pattern="^broadcast:"),
            ],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
        per_user=True,
        per_chat=True,
        # Do not use per_message=True here — it can cause subsequent user messages
        # to not be associated with the existing conversation state. The default
        # behavior (per_message=False) keeps the conversation flow working when
        # the bot asks follow-up questions like "Add question" -> expect text.
        per_message=False,
    )

    user_conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            MessageHandler(filters.Regex(_start_quiz_regex()), handle_start_quiz),
            MessageHandler(filters.Regex(_about_us_regex()), handle_about_us),
        ],
        states={
            ASK_ONBOARD_FULL_NAME: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_onboarding_name,
                )
            ],
            ASK_ONBOARD_AGE: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_onboarding_age,
                )
            ],
            ASK_ONBOARD_REGION: [
                MessageHandler(
                    filters.TEXT & ~filters.COMMAND,
                    handle_onboarding_region,
                )
            ],
        },
        fallbacks=[CommandHandler("start", cmd_start)],
        allow_reentry=True,
        per_user=True,
        per_chat=True,
        per_message=False,
    )

    app.add_handler(user_conv)
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern="^lang:"))
    app.add_handler(admin_conv)
    app.add_handler(
        MessageHandler(
            filters.Regex(_change_language_regex()),
            handle_change_language,
        )
    )
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_error_handler(on_error)
    return app
