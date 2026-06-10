"""Quiz session orchestration."""

from __future__ import annotations

import logging
import sqlite3

from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

from quiz_bot.database import (
    adb_run,
    clear_active_poll_db,
    fetch_question_db,
    get_user_progress_db,
    read_config,
    update_poll_state_db,
)
from quiz_bot.services.localization_service import resolve_language, translate
from quiz_bot.services.question_service import shuffle_options_for_poll
from quiz_bot.utils.json import parse_json_int_list, parse_options_json

logger = logging.getLogger(__name__)


async def serve_question(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
    chat_id: int,
) -> None:
    progress = await adb_run(lambda conn: get_user_progress_db(conn, user_id))
    if progress is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate("en", "send_start_first"),
        )
        return

    language_code = resolve_language(progress["language_code"])
    pool = parse_json_int_list(progress["question_ids_json"])
    index = int(progress["current_pool_index"])
    if index >= len(pool):
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(
                language_code,
                "quiz_complete",
                score=int(progress["score"]),
                total=len(pool),
            ),
            parse_mode=ParseMode.MARKDOWN,
        )
        await adb_run(lambda conn: clear_active_poll_db(conn, user_id), commit=True)
        return

    row = await adb_run(lambda conn: fetch_question_db(conn, pool[index]))
    if row is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(language_code, "question_removed"),
        )
        await adb_run(lambda conn: clear_active_poll_db(conn, user_id), commit=True)
        return

    try:
        options = parse_options_json(str(row["options_json"]))
        correct_index = int(row["correct_option_index"])
    except (ValueError, TypeError):
        logger.exception("Corrupt question row while serving question_id=%s", pool[index])
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(language_code, "question_corrupt"),
        )
        return

    if correct_index < 0 or correct_index >= len(options):
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(language_code, "question_invalid"),
        )
        return

    config = await adb_run(read_config)
    poll_options = options
    mapped_correct = correct_index
    option_order = list(range(len(options)))
    if config.shuffle_options:
        poll_options, mapped_correct, option_order = shuffle_options_for_poll(options, correct_index)

    open_period = config.question_timeout if config.question_timeout > 0 else None

    try:
        poll_message = await context.bot.send_poll(
            chat_id=chat_id,
            question=str(row["question_text"]),
            options=poll_options,
            type="quiz",
            correct_option_id=mapped_correct,
            is_anonymous=False,
            open_period=open_period,
        )
    except Forbidden:
        logger.warning("User blocked bot during active quiz user_id=%s", user_id)
        await adb_run(
            lambda conn: clear_active_poll_db(conn, user_id, session_status="abandoned"),
            commit=True,
        )
        return
    except TelegramError:
        logger.exception("Telegram API error while sending poll for user_id=%s", user_id)
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(language_code, "send_failed"),
        )
        return
    except sqlite3.Error:
        logger.exception("SQLite error while preparing poll for user_id=%s", user_id)
        return

    poll = poll_message.poll
    if poll is None or poll.id is None:
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(language_code, "poll_failed"),
        )
        return

    await adb_run(
        lambda conn: update_poll_state_db(
            conn,
            user_id,
            str(poll.id),
            mapped_correct,
            int(row["id"]),
            option_order,
        ),
        commit=True,
    )

    if open_period is not None:
        from quiz_bot.services.poll_timeout import schedule_poll_timeout

        schedule_poll_timeout(
            context,
            user_id=user_id,
            chat_id=chat_id,
            poll_id=str(poll.id),
            open_period=open_period,
        )
