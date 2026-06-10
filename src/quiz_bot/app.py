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
    ASK_CORRECT_INDEX,
    ASK_EDIT_CORRECT_INDEX,
    ASK_EDIT_OPTIONS,
    ASK_EDIT_QUESTION_TEXT,
    ASK_NUM_QUESTIONS,
    ASK_OPTIONS,
    ASK_QUESTION_TEXT,
    ASK_TIMER_SECONDS,
    AppSettings,
)
from quiz_bot.handlers.admin_handlers import (
    admin_add_correct_index,
    admin_add_options,
    admin_add_question_text,
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
from quiz_bot.handlers.user_handlers import cmd_start, handle_start_quiz
from quiz_bot.locales.messages import CHANGE_LANGUAGE_LABELS, START_QUIZ_LABELS


from telegram.request import HTTPXRequest

def _build_request(settings: AppSettings) -> HTTPXRequest:
    # Pass your read_timeout (plus padding if you want) directly into the request client
    return HTTPXRequest(
        read_timeout=settings.read_timeout + 5,
        connect_timeout=settings.connect_timeout, # or a fixed default like 5.0
    )
    
# def _build_request(settings: AppSettings) -> HTTPXRequest:
#     return HTTPXRequest(
#         connect_timeout=settings.connect_timeout,
#         read_timeout=settings.read_timeout,
#         write_timeout=settings.write_timeout,
#         pool_timeout=settings.pool_timeout,
#     )


def _start_quiz_regex() -> str:
    escaped = [re.escape(label) for label in START_QUIZ_LABELS]
    return "^(" + "|".join(escaped) + ")$"


def _change_language_regex() -> str:
    escaped = [re.escape(label) for label in CHANGE_LANGUAGE_LABELS]
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

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("language", cmd_language))
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CallbackQueryHandler(handle_language_callback, pattern="^lang:"))
    app.add_handler(admin_conv)
    app.add_handler(
        MessageHandler(
            filters.Regex(_start_quiz_regex()),
            handle_start_quiz,
        )
    )
    app.add_handler(
        MessageHandler(
            filters.Regex(_change_language_regex()),
            handle_change_language,
        )
    )
    app.add_handler(PollAnswerHandler(handle_poll_answer))
    app.add_error_handler(on_error)
    return app
