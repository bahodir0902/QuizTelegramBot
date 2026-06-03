"""Language selection handlers."""

from __future__ import annotations

import logging
import sqlite3

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from quiz_bot.database import adb_run, get_user_progress_db, set_user_language_db, upsert_user_db
from quiz_bot.keyboards import language_keyboard, main_reply_keyboard
from quiz_bot.services.localization_service import resolve_language, translate

logger = logging.getLogger(__name__)


async def cmd_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.effective_user is None:
        return
    user = update.effective_user
    try:
        await adb_run(
            lambda conn: upsert_user_db(conn, user.id, user.username, user.full_name or user.first_name or "User"),
            commit=True,
        )
    except sqlite3.Error:
        logger.exception("SQLite error while ensuring language chooser user row user_id=%s", user.id)
    if update.message is not None:
        await update.message.reply_text(
            "Choose your language.\nВыберите язык.\nTilni tanlang.",
            reply_markup=language_keyboard(),
        )


async def handle_change_language(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.message is None:
        return
    await update.message.reply_text(
        "Choose your language.\nВыберите язык.\nTilni tanlang.",
        reply_markup=language_keyboard(),
    )


async def handle_language_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = update.effective_user
    if query is None or user is None or query.data is None:
        return
    await query.answer()
    language_code = query.data.split(":", 1)[1]
    try:
        await adb_run(
            lambda conn: upsert_user_db(conn, user.id, user.username, user.full_name or user.first_name or "User"),
            commit=True,
        )
        await adb_run(
            lambda conn: set_user_language_db(conn, user.id, language_code),
            commit=True,
        )
        row = await adb_run(lambda conn: get_user_progress_db(conn, user.id))
    except sqlite3.Error:
        logger.exception("SQLite error while updating language user_id=%s", user.id)
        await query.edit_message_text(translate("en", "db_error"))
        return

    active_language = resolve_language(language_code)
    await query.edit_message_text(translate(active_language, "language_updated"))

    if row is None:
        return

    await context.bot.send_message(
        chat_id=user.id,
        text=translate(
            active_language,
            "welcome",
            start_quiz_label=translate(active_language, "start_quiz_label"),
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(active_language),
    )
