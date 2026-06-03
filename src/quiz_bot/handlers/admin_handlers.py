"""Admin handlers."""

from __future__ import annotations

import csv
import logging
import os
import sqlite3
import tempfile
from datetime import UTC, datetime

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from quiz_bot.config.constants import (
    ASK_CORRECT_INDEX,
    ASK_NUM_QUESTIONS,
    ASK_OPTIONS,
    ASK_QUESTION_TEXT,
    ASK_TIMER_SECONDS,
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
from quiz_bot.database import (
    adb_run,
    fetch_export_rows_db,
    fetch_leaderboard_db,
    insert_question_db,
    is_admin_user,
    read_config,
    toggle_config_field_db,
    update_config_field_db,
)
from quiz_bot.keyboards import admin_dashboard_keyboard, admin_settings_keyboard
from quiz_bot.services.localization_service import language_for_user, translate
from quiz_bot.utils.names import user_display_name
from quiz_bot.utils.telegram import safe_edit_message_text

logger = logging.getLogger(__name__)


async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    del context
    if update.effective_user is None or update.message is None:
        return
    user_id = update.effective_user.id
    language_code = await language_for_user(user_id)
    try:
        admin = await adb_run(lambda conn: is_admin_user(conn, user_id))
    except sqlite3.Error:
        logger.exception("SQLite error while verifying admin user_id=%s", user_id)
        await update.message.reply_text(translate(language_code, "db_error"))
        return

    if not admin:
        await update.message.reply_text(translate(language_code, "admin_denied"))
        return

    await update.message.reply_text(
        f"*{translate(language_code, 'admin_dashboard')}*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_dashboard_keyboard(language_code),
    )


async def admin_callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return None

    await query.answer()
    user_id = update.effective_user.id
    language_code = await language_for_user(user_id)

    try:
        admin = await adb_run(lambda conn: is_admin_user(conn, user_id))
    except sqlite3.Error:
        logger.exception("SQLite error while routing admin callback user_id=%s", user_id)
        await safe_edit_message_text(query, translate(language_code, "db_error"))
        return ConversationHandler.END

    if not admin:
        await safe_edit_message_text(query, translate(language_code, "admin_denied"))
        return ConversationHandler.END

    data = query.data
    dashboard = admin_dashboard_keyboard(language_code)

    if data == CB_ADMIN_STATS:
        try:
            rows = await adb_run(fetch_leaderboard_db)
        except sqlite3.Error:
            logger.exception("SQLite error while loading stats user_id=%s", user_id)
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_stats_failed"),
            )
            return ConversationHandler.END

        if not rows:
            await safe_edit_message_text(
                query,
                translate(language_code, "stats_empty"),
                reply_markup=dashboard,
                unchanged_hint=translate(language_code, "stats_up_to_date"),
            )
            return ConversationHandler.END

        lines = [f"*{translate(language_code, 'leaderboard_title')}*"]
        for rank, row in enumerate(rows, start=1):
            lines.append(
                translate(
                    language_code,
                    "leaderboard_row",
                    rank=rank,
                    name=user_display_name(row),
                    score=int(row["score"]),
                )
            )
        await safe_edit_message_text(
            query,
            "\n".join(lines),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dashboard,
            unchanged_hint=translate(language_code, "stats_up_to_date"),
        )
        return ConversationHandler.END

    if data == CB_ADMIN_EXPORT:
        try:
            rows = await adb_run(fetch_export_rows_db)
        except sqlite3.Error:
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_stats_failed"),
            )
            return ConversationHandler.END

        temp_path: str | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".csv",
                delete=False,
                newline="",
                encoding="utf-8",
            ) as temp_file:
                writer = csv.writer(temp_file)
                writer.writerow(["username", "full_name", "score"])
                for row in rows:
                    writer.writerow([row["username"] or "", row["full_name"] or "", int(row["score"])])
                temp_path = temp_file.name

            chat_id = query.message.chat_id if query.message is not None else user_id
            with open(temp_path, "rb") as file_handle:
                await context.bot.send_document(
                    chat_id=chat_id,
                    document=file_handle,
                    filename=f"quiz_export_{datetime.now(UTC):%Y%m%d_%H%M%S}.csv",
                    caption=translate(language_code, "admin_export_caption"),
                )
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_export_sent"),
                reply_markup=dashboard,
            )
        except OSError:
            logger.exception("Filesystem error while exporting CSV user_id=%s", user_id)
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_export_file_failed"),
            )
        except TelegramError:
            logger.exception("Telegram error while sending export user_id=%s", user_id)
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_export_failed"),
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    logger.warning("Could not remove temporary export file path=%s", temp_path)
        return ConversationHandler.END

    if data == CB_ADMIN_SETTINGS:
        try:
            config = await adb_run(read_config)
        except sqlite3.Error:
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_settings_load_failed"),
            )
            return ConversationHandler.END
        await safe_edit_message_text(
            query,
            f"*{translate(language_code, 'settings')}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_settings_keyboard(config, language_code),
        )
        return ConversationHandler.END

    if data == CB_ADMIN_BACK:
        await safe_edit_message_text(
            query,
            f"*{translate(language_code, 'admin_dashboard')}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dashboard,
        )
        return ConversationHandler.END

    if data == CB_TOGGLE_Q_SHUFFLE:
        try:
            config = await adb_run(
                lambda conn: toggle_config_field_db(conn, "shuffle_questions"),
                commit=True,
            )
        except sqlite3.Error:
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_settings_failed"),
            )
            return ConversationHandler.END
        await safe_edit_message_text(
            query,
            f"*{translate(language_code, 'settings_updated')}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_settings_keyboard(config, language_code),
        )
        return ConversationHandler.END

    if data == CB_TOGGLE_OPT_SHUFFLE:
        try:
            config = await adb_run(
                lambda conn: toggle_config_field_db(conn, "shuffle_options"),
                commit=True,
            )
        except sqlite3.Error:
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_settings_failed"),
            )
            return ConversationHandler.END
        await safe_edit_message_text(
            query,
            f"*{translate(language_code, 'settings_updated')}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=admin_settings_keyboard(config, language_code),
        )
        return ConversationHandler.END

    if data == CB_ADMIN_ADD:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_add_question_prompt"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_QUESTION_TEXT

    if data == CB_SET_LIMIT:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_set_limit_prompt"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_NUM_QUESTIONS

    if data == CB_SET_TIMER:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_set_timer_prompt"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_TIMER_SECONDS

    return ConversationHandler.END


async def _admin_language(update: Update) -> str:
    if update.effective_user is None:
        return "en"
    return await language_for_user(update.effective_user.id)


async def admin_add_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(translate(language_code, "admin_question_text_empty"))
        return ASK_QUESTION_TEXT

    context.user_data["new_question_text"] = text
    await update.message.reply_text(
        translate(language_code, "admin_add_options_prompt"),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_OPTIONS


async def admin_add_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    raw = (update.message.text or "").strip()
    options = [part.strip() for part in raw.split(",") if part.strip()]
    if len(options) < 2:
        await update.message.reply_text(translate(language_code, "admin_options_invalid"))
        return ASK_OPTIONS

    context.user_data["new_options"] = options
    await update.message.reply_text(
        translate(language_code, "admin_add_index_prompt", max_index=len(options) - 1),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_CORRECT_INDEX


async def admin_add_correct_index(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    raw = (update.message.text or "").strip()
    options = context.user_data.get("new_options", [])
    question_text = context.user_data.get("new_question_text", "")
    try:
        index = int(raw)
    except ValueError:
        await update.message.reply_text(translate(language_code, "admin_index_invalid"))
        return ASK_CORRECT_INDEX

    if index < 0 or index >= len(options):
        await update.message.reply_text(
            translate(language_code, "admin_index_range", max_index=len(options) - 1)
        )
        return ASK_CORRECT_INDEX

    try:
        await adb_run(
            lambda conn: insert_question_db(conn, question_text, options, index),
            commit=True,
        )
    except sqlite3.Error:
        logger.exception("SQLite error while inserting question admin_user_id=%s", update.effective_user.id)
        await update.message.reply_text(translate(language_code, "admin_question_save_failed"))
        return ConversationHandler.END

    context.user_data.pop("new_question_text", None)
    context.user_data.pop("new_options", None)
    await update.message.reply_text(
        translate(language_code, "admin_question_added"),
        reply_markup=admin_dashboard_keyboard(language_code),
    )
    return ConversationHandler.END


async def admin_set_num_questions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    try:
        value = int((update.message.text or "").strip())
    except ValueError:
        await update.message.reply_text(translate(language_code, "admin_integer_required"))
        return ASK_NUM_QUESTIONS

    if value < 1 or value > 100:
        await update.message.reply_text(translate(language_code, "admin_limit_range"))
        return ASK_NUM_QUESTIONS

    try:
        config = await adb_run(
            lambda conn: (update_config_field_db(conn, "num_questions", value), read_config(conn))[1],
            commit=True,
        )
    except sqlite3.Error:
        await update.message.reply_text(translate(language_code, "admin_limit_failed"))
        return ConversationHandler.END

    await update.message.reply_text(
        translate(language_code, "admin_limit_set", value=value),
        reply_markup=admin_settings_keyboard(config, language_code),
    )
    return ConversationHandler.END


async def admin_set_timer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    try:
        value = int((update.message.text or "").strip())
    except ValueError:
        await update.message.reply_text(translate(language_code, "admin_integer_required"))
        return ASK_TIMER_SECONDS

    if value < 0 or value > 600:
        await update.message.reply_text(translate(language_code, "admin_timer_range"))
        return ASK_TIMER_SECONDS

    try:
        config = await adb_run(
            lambda conn: (update_config_field_db(conn, "question_timeout", value), read_config(conn))[1],
            commit=True,
        )
    except sqlite3.Error:
        await update.message.reply_text(translate(language_code, "admin_timer_failed"))
        return ConversationHandler.END

    message_key = "admin_timer_set_disabled" if value == 0 else "admin_timer_set"
    await update.message.reply_text(
        translate(language_code, message_key, value=value),
        reply_markup=admin_settings_keyboard(config, language_code),
    )
    return ConversationHandler.END
