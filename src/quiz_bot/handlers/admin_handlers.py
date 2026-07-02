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
    ASK_EDIT_CORRECT_INDEX,
    ASK_EDIT_ABOUT_TEXT,
    ASK_EDIT_OPTIONS,
    ASK_CHANNEL_URL,
    ASK_EDIT_CHANNEL_URL,
    ASK_EDIT_QUESTION_TEXT,
    ASK_CORRECT_INDEX,
    ASK_NUM_QUESTIONS,
    ASK_OPTIONS,
    ASK_QUESTION_TEXT,
    ASK_TIMER_SECONDS,
    ASK_BROADCAST_TEXT,
    ASK_BROADCAST_CONFIRM,
    CB_ADMIN_ADD,
    CB_ADMIN_ABOUT,
    CB_ADMIN_BACK,
    CB_BROADCAST_CANCEL,
    CB_BROADCAST_SEND,
    CB_ADMIN_CHANNELS,
    CB_ADMIN_EXPORT,
    CB_ADMIN_QUESTIONS,
    CB_ADMIN_SETTINGS,
    CB_ADMIN_SEND_MESSAGE,
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
    CB_CHANNEL_ADD,
    CB_CHANNEL_DELETE_CONFIRM_PREFIX,
    CB_CHANNEL_DELETE_PREFIX,
    CB_CHANNEL_EDIT_PREFIX,
    CB_CHANNEL_TOGGLE_REQUIRE_PREFIX,
    CB_TOGGLE_OPT_SHUFFLE,
    CB_TOGGLE_Q_SHUFFLE,
)
from quiz_bot.database import (
    adb_run,
    create_channel_db,
    delete_channel_db,
    delete_question_db,
    delete_question_option_db,
    fetch_export_rows_db,
    fetch_leaderboard_db,
    count_user_progress_rows_db,
    fetch_question_db,
    fetch_question_stats_db,
    list_channels_db,
    insert_question_db,
    is_admin_user,
    list_user_progress_rows_db,
    list_questions_db,
    list_registered_users_db,
    read_config,
    replace_question_options_db,
    toggle_config_field_db,
    toggle_channel_required_db,
    update_config_field_db,
    update_channel_db,
    update_about_bot_text_db,
    update_question_correct_index_db,
    update_question_text_db,
)
from quiz_bot.keyboards import (
    admin_channel_delete_keyboard,
    admin_channels_keyboard,
    admin_broadcast_confirm_keyboard,
    admin_dashboard_keyboard,
    admin_question_delete_keyboard,
    admin_question_detail_keyboard,
    admin_question_options_keyboard,
    admin_questions_keyboard,
    admin_settings_keyboard,
    admin_users_pagination_keyboard,
)
from quiz_bot.services.channel_service import parse_channel_reference
from quiz_bot.services.localization_service import language_for_user, translate
from quiz_bot.utils.json import parse_options_json
from quiz_bot.utils.names import user_display_name
from quiz_bot.utils.telegram import safe_edit_message_text

logger = logging.getLogger(__name__)


def _callback_id(data: str, prefix: str) -> int | None:
    if not data.startswith(prefix):
        return None
    try:
        return int(data.removeprefix(prefix))
    except ValueError:
        return None


def _parse_question_option_callback(data: str) -> tuple[int, int] | None:
    if not data.startswith(CB_QUESTION_DELETE_OPTION_PREFIX):
        return None
    payload = data.removeprefix(CB_QUESTION_DELETE_OPTION_PREFIX)
    try:
        question_id_raw, option_index_raw = payload.split(":", maxsplit=1)
        return int(question_id_raw), int(option_index_raw)
    except ValueError:
        return None


def _parse_options(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


def _question_detail_text(language_code: str, stats: dict[str, object]) -> str:
    row = stats["question"]
    options = parse_options_json(str(row["options_json"]))
    correct_index = int(row["correct_option_index"])
    attempts = int(stats["attempts"])
    correct = int(stats["correct"])
    answered = int(stats["answered"])
    timed_out = int(stats["timed_out"])
    option_counts = stats["option_counts"]
    assert isinstance(option_counts, dict)
    accuracy = round((correct / answered) * 100, 1) if answered else 0

    lines = [
        translate(language_code, "admin_question_detail_title", id=int(row["id"])),
        str(row["question_text"]),
        "",
        translate(
            language_code,
            "admin_question_summary",
            attempts=attempts,
            answered=answered,
            correct=correct,
            timed_out=timed_out,
            accuracy=accuracy,
        ),
        "",
        translate(language_code, "admin_options_title"),
    ]
    for index, option in enumerate(options):
        selected_count = int(option_counts.get(index, 0))
        correct_marker = " ✓" if index == correct_index else ""
        lines.append(
            translate(
                language_code,
                "admin_option_stats_row",
                index=index,
                option=option,
                selected=selected_count,
                correct=correct_marker,
            )
        )
    return "\n".join(lines)


async def _show_question_list(query, language_code: str) -> None:
    rows = await adb_run(list_questions_db)
    if not rows:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_questions_empty"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return
    await safe_edit_message_text(
        query,
        translate(language_code, "admin_questions_title"),
        reply_markup=admin_questions_keyboard(rows, language_code),
    )


ADMIN_USERS_PAGE_SIZE = 5


def _admin_user_value(value: object, default: str = "—") -> str:
    if value in (None, ""):
        return default
    return str(value)


def _admin_user_profile(row: sqlite3.Row) -> str:
    parts = [
        _admin_user_value(row["first_name"]),
        _admin_user_value(row["last_name"]),
        _admin_user_value(row["age"]),
        _admin_user_value(row["region"]),
    ]
    return " / ".join(parts)


def _admin_user_status(row: sqlite3.Row, language_code: str) -> str:
    if int(row["onboarding_completed"] or 0) == 1:
        return translate(language_code, "admin_users_profile_completed")
    return translate(
        language_code,
        "admin_users_profile_incomplete",
        step=_admin_user_value(row["onboarding_step"], "not started"),
    )


def _admin_users_text(
    rows: list[sqlite3.Row],
    language_code: str,
    *,
    page: int,
    total_count: int,
    total_pages: int,
) -> str:
    lines = [
        f"*{translate(language_code, 'admin_users_title', count=total_count, page=page, total_pages=total_pages)}*"
    ]
    for row in rows:
        username = _admin_user_value(row["username"], "—")
        lines.extend(
            [
                "",
                translate(
                    language_code,
                    "admin_users_row",
                    user_id=int(row["user_id"]),
                    name=user_display_name(row),
                    username=username,
                    language=_admin_user_value(row["language_code"]),
                    profile_status=_admin_user_status(row, language_code),
                    score=int(row["score"] or 0),
                    profile=_admin_user_profile(row),
                    session_status=_admin_user_value(row["session_status"]),
                    started=_admin_user_value(row["start_time"]),
                    finished=_admin_user_value(row["finished_time"]),
                ),
            ]
        )
    return "\n".join(lines)


async def _show_users_list(query, language_code: str, page: int = 1) -> None:
    total_count = await adb_run(count_user_progress_rows_db)
    if total_count == 0:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_users_empty"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return

    total_pages = max(1, (total_count + ADMIN_USERS_PAGE_SIZE - 1) // ADMIN_USERS_PAGE_SIZE)
    page = min(max(page, 1), total_pages)
    offset = (page - 1) * ADMIN_USERS_PAGE_SIZE
    rows = await adb_run(
        lambda conn: list_user_progress_rows_db(
            conn,
            limit=ADMIN_USERS_PAGE_SIZE,
            offset=offset,
        )
    )
    await safe_edit_message_text(
        query,
        _admin_users_text(
            rows,
            language_code,
            page=page,
            total_count=total_count,
            total_pages=total_pages,
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=admin_users_pagination_keyboard(
            language_code,
            page=page,
            total_pages=total_pages,
        ),
    )


async def _show_question_detail(query, question_id: int, language_code: str) -> None:
    stats = await adb_run(lambda conn: fetch_question_stats_db(conn, question_id))
    if stats is None:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_question_missing"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return
    await safe_edit_message_text(
        query,
        _question_detail_text(language_code, stats),
        reply_markup=admin_question_detail_keyboard(question_id, language_code),
    )


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

    if data == CB_ADMIN_CHANNELS:
        rows = await adb_run(list_channels_db)
        text = translate(language_code, "admin_channels_title") if rows else translate(language_code, "admin_channels_empty")
        await safe_edit_message_text(query, text, reply_markup=admin_channels_keyboard(rows, language_code))
        return ConversationHandler.END

    if data == CB_CHANNEL_ADD:
        await safe_edit_message_text(query, translate(language_code, "admin_channel_prompt"), parse_mode=ParseMode.MARKDOWN)
        return ASK_CHANNEL_URL

    channel_id = _callback_id(data, CB_CHANNEL_TOGGLE_REQUIRE_PREFIX)
    if channel_id is not None:
        await adb_run(lambda conn: toggle_channel_required_db(conn, channel_id), commit=True)
        rows = await adb_run(list_channels_db)
        await safe_edit_message_text(query, translate(language_code, "admin_channels_title"), reply_markup=admin_channels_keyboard(rows, language_code))
        return ConversationHandler.END

    channel_id = _callback_id(data, CB_CHANNEL_EDIT_PREFIX)
    if channel_id is not None:
        context.user_data["edit_channel_id"] = channel_id
        await safe_edit_message_text(query, translate(language_code, "admin_channel_prompt"), parse_mode=ParseMode.MARKDOWN)
        return ASK_EDIT_CHANNEL_URL

    channel_id = _callback_id(data, CB_CHANNEL_DELETE_CONFIRM_PREFIX)
    if channel_id is not None:
        await safe_edit_message_text(query, translate(language_code, "admin_channel_delete_confirm", id=channel_id), reply_markup=admin_channel_delete_keyboard(channel_id, language_code))
        return ConversationHandler.END

    channel_id = _callback_id(data, CB_CHANNEL_DELETE_PREFIX)
    if channel_id is not None:
        ok = await adb_run(lambda conn: delete_channel_db(conn, channel_id), commit=True)
        rows = await adb_run(list_channels_db)
        text = translate(language_code, "admin_channel_deleted" if ok else "admin_channel_missing")
        await safe_edit_message_text(query, text, reply_markup=admin_channels_keyboard(rows, language_code))
        return ConversationHandler.END


    if data == CB_ADMIN_USERS:
        await _show_users_list(query, language_code)
        return ConversationHandler.END

    user_page = _callback_id(data, CB_ADMIN_USERS_PAGE_PREFIX)
    if user_page is not None:
        await _show_users_list(query, language_code, page=user_page)
        return ConversationHandler.END

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
                writer.writerow(
                    [
                        "username",
                        "full_name",
                        "first_name",
                        "last_name",
                        "age",
                        "region",
                        "score",
                        "last_duration_seconds",
                    ]
                )
                for row in rows:
                    writer.writerow(
                        [
                            row["username"] or "",
                            row["full_name"] or "",
                            row["first_name"] or "",
                            row["last_name"] or "",
                            row["age"] if row["age"] is not None else "",
                            row["region"] or "",
                            int(row["score"]),
                            row["last_duration_seconds"]
                            if row["last_duration_seconds"] is not None
                            else "",
                        ]
                    )
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

    if data == CB_ADMIN_ABOUT:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_about_language_prompt"),
            reply_markup=admin_about_language_keyboard(language_code),
        )
        return ConversationHandler.END

    if data.startswith(CB_EDIT_ABOUT_PREFIX):
        about_language = data.removeprefix(CB_EDIT_ABOUT_PREFIX)
        if about_language not in {"uz", "ru", "en"}:
            await safe_edit_message_text(query, translate(language_code, "admin_settings_failed"))
            return ConversationHandler.END
        context.user_data["edit_about_language"] = about_language
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_edit_about_prompt", language=about_language),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_EDIT_ABOUT_TEXT

    if data == CB_ADMIN_BACK:
        await safe_edit_message_text(
            query,
            f"*{translate(language_code, 'admin_dashboard')}*",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=dashboard,
        )
        return ConversationHandler.END

    if data == CB_ADMIN_QUESTIONS:
        try:
            await _show_question_list(query, language_code)
        except (sqlite3.Error, ValueError):
            logger.exception("Failed to load question list user_id=%s", user_id)
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_questions_failed"),
                reply_markup=dashboard,
            )
        return ConversationHandler.END

    question_id = _callback_id(data, CB_QUESTION_VIEW_PREFIX)
    if question_id is not None:
        try:
            await _show_question_detail(query, question_id, language_code)
        except (sqlite3.Error, ValueError):
            logger.exception("Failed to load question detail question_id=%s", question_id)
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_question_load_failed"),
                reply_markup=dashboard,
            )
        return ConversationHandler.END

    question_id = _callback_id(data, CB_QUESTION_EDIT_TEXT_PREFIX)
    if question_id is not None:
        context.user_data["edit_question_id"] = question_id
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_edit_question_text_prompt"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_EDIT_QUESTION_TEXT

    question_id = _callback_id(data, CB_QUESTION_EDIT_OPTIONS_PREFIX)
    if question_id is not None:
        context.user_data["edit_question_id"] = question_id
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_edit_options_prompt"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_EDIT_OPTIONS

    question_id = _callback_id(data, CB_QUESTION_EDIT_CORRECT_PREFIX)
    if question_id is not None:
        context.user_data["edit_question_id"] = question_id
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_edit_correct_prompt"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_EDIT_CORRECT_INDEX

    question_id = _callback_id(data, CB_QUESTION_DELETE_CONFIRM_PREFIX)
    if question_id is not None:
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_delete_question_confirm", id=question_id),
            reply_markup=admin_question_delete_keyboard(question_id, language_code),
        )
        return ConversationHandler.END

    question_id = _callback_id(data, CB_QUESTION_DELETE_PREFIX)
    if question_id is not None:
        try:
            deleted = await adb_run(
                lambda conn: delete_question_db(conn, question_id),
                commit=True,
                immediate=True,
            )
            if deleted:
                await safe_edit_message_text(
                    query,
                    translate(language_code, "admin_question_deleted"),
                    reply_markup=dashboard,
                )
            else:
                await safe_edit_message_text(
                    query,
                    translate(language_code, "admin_question_missing"),
                    reply_markup=dashboard,
                )
        except sqlite3.Error:
            logger.exception("Failed to delete question question_id=%s", question_id)
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_question_delete_failed"),
                reply_markup=dashboard,
            )
        return ConversationHandler.END

    question_id = _callback_id(data, CB_QUESTION_OPTIONS_PREFIX)
    if question_id is not None:
        try:
            row = await adb_run(lambda conn: fetch_question_db(conn, question_id))
            if row is None:
                await safe_edit_message_text(
                    query,
                    translate(language_code, "admin_question_missing"),
                    reply_markup=dashboard,
                )
                return ConversationHandler.END
            options = parse_options_json(str(row["options_json"]))
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_manage_options_title", id=question_id),
                reply_markup=admin_question_options_keyboard(question_id, options, language_code),
            )
        except (sqlite3.Error, ValueError):
            logger.exception("Failed to load question options question_id=%s", question_id)
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_question_load_failed"),
                reply_markup=dashboard,
            )
        return ConversationHandler.END

    option_payload = _parse_question_option_callback(data)
    if option_payload is not None:
        question_id, option_index = option_payload
        try:
            deleted, status = await adb_run(
                lambda conn: delete_question_option_db(conn, question_id, option_index),
                commit=True,
                immediate=True,
            )
            if deleted:
                await _show_question_detail(query, question_id, language_code)
            else:
                await safe_edit_message_text(
                    query,
                    translate(language_code, f"admin_option_delete_{status}"),
                    reply_markup=admin_question_detail_keyboard(question_id, language_code),
                )
        except (sqlite3.Error, ValueError):
            logger.exception(
                "Failed to delete option question_id=%s option_index=%s",
                question_id,
                option_index,
            )
            await safe_edit_message_text(
                query,
                translate(language_code, "admin_option_delete_failed"),
                reply_markup=admin_question_detail_keyboard(question_id, language_code),
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

    if data == CB_ADMIN_BROADCAST:
        context.user_data.pop("broadcast_text", None)
        await safe_edit_message_text(
            query,
            translate(language_code, "admin_broadcast_prompt"),
            parse_mode=ParseMode.MARKDOWN,
        )
        return ASK_BROADCAST_TEXT

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
    options = _parse_options(raw)
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


async def _reply_question_detail(update: Update, question_id: int, language_code: str) -> None:
    if update.message is None:
        return
    stats = await adb_run(lambda conn: fetch_question_stats_db(conn, question_id))
    if stats is None:
        await update.message.reply_text(
            translate(language_code, "admin_question_missing"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return
    await update.message.reply_text(
        _question_detail_text(language_code, stats),
        reply_markup=admin_question_detail_keyboard(question_id, language_code),
    )


async def admin_edit_question_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    question_id = context.user_data.get("edit_question_id")
    if not isinstance(question_id, int):
        await update.message.reply_text(
            translate(language_code, "admin_question_missing"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return ConversationHandler.END

    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(translate(language_code, "admin_question_text_empty"))
        return ASK_EDIT_QUESTION_TEXT

    try:
        updated = await adb_run(
            lambda conn: update_question_text_db(conn, question_id, text),
            commit=True,
            immediate=True,
        )
    except sqlite3.Error:
        logger.exception("SQLite error while updating question text question_id=%s", question_id)
        await update.message.reply_text(translate(language_code, "admin_question_update_failed"))
        return ConversationHandler.END

    context.user_data.pop("edit_question_id", None)
    if not updated:
        await update.message.reply_text(
            translate(language_code, "admin_question_missing"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return ConversationHandler.END
    await update.message.reply_text(translate(language_code, "admin_question_updated"))
    await _reply_question_detail(update, question_id, language_code)
    return ConversationHandler.END


async def admin_edit_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    options = _parse_options((update.message.text or "").strip())
    if len(options) < 2:
        await update.message.reply_text(translate(language_code, "admin_options_invalid"))
        return ASK_EDIT_OPTIONS

    context.user_data["edit_options"] = options
    await update.message.reply_text(
        translate(language_code, "admin_add_index_prompt", max_index=len(options) - 1),
        parse_mode=ParseMode.MARKDOWN,
    )
    return ASK_EDIT_CORRECT_INDEX


async def admin_edit_correct_index(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END

    question_id = context.user_data.get("edit_question_id")
    if not isinstance(question_id, int):
        await update.message.reply_text(
            translate(language_code, "admin_question_missing"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return ConversationHandler.END

    raw = (update.message.text or "").strip()
    try:
        index = int(raw)
    except ValueError:
        await update.message.reply_text(translate(language_code, "admin_index_invalid"))
        return ASK_EDIT_CORRECT_INDEX

    pending_options = context.user_data.get("edit_options")
    try:
        if isinstance(pending_options, list):
            options = [str(option) for option in pending_options]
            if index < 0 or index >= len(options):
                await update.message.reply_text(
                    translate(language_code, "admin_index_range", max_index=len(options) - 1)
                )
                return ASK_EDIT_CORRECT_INDEX
            updated = await adb_run(
                lambda conn: replace_question_options_db(conn, question_id, options, index),
                commit=True,
                immediate=True,
            )
        else:
            row = await adb_run(lambda conn: fetch_question_db(conn, question_id))
            if row is None:
                await update.message.reply_text(
                    translate(language_code, "admin_question_missing"),
                    reply_markup=admin_dashboard_keyboard(language_code),
                )
                return ConversationHandler.END
            options = parse_options_json(str(row["options_json"]))
            if index < 0 or index >= len(options):
                await update.message.reply_text(
                    translate(language_code, "admin_index_range", max_index=len(options) - 1)
                )
                return ASK_EDIT_CORRECT_INDEX
            updated = await adb_run(
                lambda conn: update_question_correct_index_db(conn, question_id, index),
                commit=True,
                immediate=True,
            )
    except (sqlite3.Error, ValueError):
        logger.exception("SQLite error while updating question options question_id=%s", question_id)
        await update.message.reply_text(translate(language_code, "admin_question_update_failed"))
        return ConversationHandler.END

    context.user_data.pop("edit_question_id", None)
    context.user_data.pop("edit_options", None)
    if not updated:
        await update.message.reply_text(
            translate(language_code, "admin_question_missing"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
        return ConversationHandler.END
    await update.message.reply_text(translate(language_code, "admin_question_updated"))
    await _reply_question_detail(update, question_id, language_code)
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


async def admin_add_channel_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END
    language_code = await language_for_user(update.effective_user.id)
    parsed = parse_channel_reference(update.message.text or "")
    if parsed is None:
        await update.message.reply_text(translate(language_code, "admin_channel_invalid"))
        return ASK_CHANNEL_URL
    await adb_run(lambda conn: create_channel_db(conn, parsed.title, parsed.url, parsed.username), commit=True)
    rows = await adb_run(list_channels_db)
    await update.message.reply_text(translate(language_code, "admin_channel_added"), reply_markup=admin_channels_keyboard(rows, language_code))
    return ConversationHandler.END


async def admin_edit_channel_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END
    language_code = await language_for_user(update.effective_user.id)
    channel_id = int(context.user_data.get("edit_channel_id", 0))
    parsed = parse_channel_reference(update.message.text or "")
    if channel_id <= 0 or parsed is None:
        await update.message.reply_text(translate(language_code, "admin_channel_invalid"))
        return ASK_EDIT_CHANNEL_URL
    ok = await adb_run(lambda conn: update_channel_db(conn, channel_id, parsed.title, parsed.url, parsed.username), commit=True)
    rows = await adb_run(list_channels_db)
    await update.message.reply_text(translate(language_code, "admin_channel_updated" if ok else "admin_channel_missing"), reply_markup=admin_channels_keyboard(rows, language_code))
    return ConversationHandler.END

async def admin_broadcast_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(translate(language_code, "admin_broadcast_empty"))
        return ASK_BROADCAST_TEXT
    context.user_data["broadcast_text"] = text
    await update.message.reply_text(
        translate(language_code, "admin_broadcast_confirm_prompt", message=text),
        reply_markup=admin_broadcast_confirm_keyboard(language_code),
    )
    return ASK_BROADCAST_CONFIRM


async def admin_broadcast_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    if query is None or query.data is None or update.effective_user is None:
        return ConversationHandler.END
    await query.answer()
    user_id = update.effective_user.id
    language_code = await language_for_user(user_id)
    dashboard = admin_dashboard_keyboard(language_code)
    if not await adb_run(lambda conn: is_admin_user(conn, user_id)):
        await safe_edit_message_text(query, translate(language_code, "permission_denied"))
        return ConversationHandler.END
    if query.data == CB_BROADCAST_CANCEL:
        context.user_data.pop("broadcast_text", None)
        await safe_edit_message_text(query, translate(language_code, "admin_broadcast_cancelled"), reply_markup=dashboard)
        return ConversationHandler.END
    if query.data != CB_BROADCAST_SEND:
        return ASK_BROADCAST_CONFIRM
    text = str(context.user_data.get("broadcast_text", "")).strip()
    if not text:
        await safe_edit_message_text(query, translate(language_code, "admin_broadcast_empty"))
        return ASK_BROADCAST_TEXT
    users = await adb_run(list_registered_users_db)
    success_count = failure_count = 0
    for row in users:
        try:
            await context.bot.send_message(chat_id=int(row["user_id"]), text=text)
            success_count += 1
        except TelegramError:
            failure_count += 1
    context.user_data.pop("broadcast_text", None)
    await safe_edit_message_text(query, translate(language_code, "admin_broadcast_report", success=success_count, failure=failure_count), reply_markup=dashboard)
    return ConversationHandler.END


async def admin_edit_about_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    language_code = await _admin_language(update)
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END
    if not await adb_run(lambda conn: is_admin_user(conn, update.effective_user.id)):
        await update.message.reply_text(translate(language_code, "permission_denied"))
        return ConversationHandler.END
    text = (update.message.text or "").strip()
    if not text:
        await update.message.reply_text(translate(language_code, "admin_about_text_empty"))
        return ASK_EDIT_ABOUT_TEXT
    about_language = context.user_data.get("edit_about_language", language_code)
    await adb_run(lambda conn: update_about_bot_text_db(conn, str(about_language), text), commit=True)
    context.user_data.pop("edit_about_language", None)
    await update.message.reply_text(translate(language_code, "admin_about_text_updated"), reply_markup=admin_dashboard_keyboard(language_code))
    return ConversationHandler.END
