"""User-facing handlers."""

from __future__ import annotations

import logging
import sqlite3

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from quiz_bot.database import adb_run, get_user_progress_db, start_quiz_session_db, upsert_user_db
from quiz_bot.domain import QuizStartError
from quiz_bot.keyboards import language_keyboard, main_reply_keyboard
from quiz_bot.services.localization_service import resolve_language, translate
from quiz_bot.services.quiz_service import serve_question

logger = logging.getLogger(__name__)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None:
        return
    user = update.effective_user
    full_name = user.full_name or user.first_name or "User"

    try:
        existing = await adb_run(lambda conn: get_user_progress_db(conn, user.id))
        await adb_run(
            lambda conn: upsert_user_db(conn, user.id, user.username, full_name),
            commit=True,
        )
        progress = await adb_run(lambda conn: get_user_progress_db(conn, user.id))
    except sqlite3.Error:
        logger.exception("SQLite error during /start registration user_id=%s", user.id)
        if update.message is not None:
            await update.message.reply_text(translate("en", "db_error"))
        return

    if progress is None:
        return

    if existing is None or progress["language_code"] in (None, ""):
        if update.message is not None:
            await update.message.reply_text(
                translate("en", "language_prompt"),
                reply_markup=language_keyboard(),
            )
        return

    language_code = resolve_language(progress["language_code"])
    text = translate(
        language_code,
        "welcome",
        start_quiz_label=translate(language_code, "start_quiz_label"),
    )
    if update.message is not None:
        await update.message.reply_text(
            text,
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_reply_keyboard(language_code),
        )


async def handle_start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user is None or update.message is None:
        return
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    progress = await adb_run(lambda conn: get_user_progress_db(conn, user_id))
    language_code = resolve_language(progress["language_code"] if progress else "en")

    try:
        pool = await adb_run(
            lambda conn: start_quiz_session_db(conn, user_id),
            commit=True,
            immediate=True,
        )
    except QuizStartError as exc:
        message_key = "no_questions" if str(exc) == "NO_QUESTIONS" else "empty_pool"
        await update.message.reply_text(translate(language_code, message_key))
        return
    except sqlite3.Error:
        logger.exception("SQLite error while starting quiz user_id=%s", user_id)
        await update.message.reply_text(translate(language_code, "db_error"))
        return

    await update.message.reply_text(
        translate(language_code, "quiz_started", count=len(pool)),
        reply_markup=main_reply_keyboard(language_code),
    )
    await serve_question(context, user_id, chat_id)
