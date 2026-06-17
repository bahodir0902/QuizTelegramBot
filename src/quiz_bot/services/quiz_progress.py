"""Shared quiz progression after an answer or timeout."""

from __future__ import annotations

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from quiz_bot.database import adb_run, complete_quiz_session_db
from quiz_bot.keyboards import main_reply_keyboard
from quiz_bot.services.localization_service import resolve_language, translate
from quiz_bot.services.onboarding_service import format_duration
from quiz_bot.services.quiz_service import serve_question
from quiz_bot.utils.json import parse_json_int_list


async def continue_quiz_or_finish(
    context: ContextTypes.DEFAULT_TYPE,
    updated,
    chat_id: int,
) -> None:
    language_code = resolve_language(updated["language_code"])
    pool = parse_json_int_list(updated["question_ids_json"])
    new_index = int(updated["current_pool_index"])
    user_id = int(updated["user_id"])

    if new_index >= len(pool):
        completed = await adb_run(
            lambda conn: complete_quiz_session_db(conn, user_id),
            commit=True,
        )
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(
                language_code,
                "quiz_complete_timed",
                score=int(completed["score"]),
                total=len(pool),
                duration=format_duration(completed["last_duration_seconds"]),
            ),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_reply_keyboard(language_code),
        )
        return

    await serve_question(context, user_id, chat_id)
