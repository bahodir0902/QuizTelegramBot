"""Shared quiz progression after an answer or timeout."""

from __future__ import annotations

from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from quiz_bot.keyboards import main_reply_keyboard
from quiz_bot.services.localization_service import resolve_language, translate
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
    score = int(updated["score"])
    user_id = int(updated["user_id"])

    if new_index >= len(pool):
        await context.bot.send_message(
            chat_id=chat_id,
            text=translate(language_code, "quiz_complete", score=score, total=len(pool)),
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=main_reply_keyboard(language_code),
        )
        return

    await serve_question(context, user_id, chat_id)
