"""Poll answer handlers."""

from __future__ import annotations

import logging
import sqlite3

from telegram import Update
from telegram.ext import ContextTypes

from quiz_bot.services.poll_timeout import cancel_poll_timeout
from quiz_bot.services.quiz_progress import continue_quiz_or_finish
from quiz_bot.services.scoring_service import score_poll_answer

logger = logging.getLogger(__name__)


async def handle_poll_answer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    poll_answer = update.poll_answer
    if poll_answer is None or not poll_answer.option_ids:
        return

    poll_id = str(poll_answer.poll_id)
    selected = int(poll_answer.option_ids[0])
    cancel_poll_timeout(poll_id, context)

    try:
        updated, status = await score_poll_answer(
            poll_id,
            poll_answer.user.id,
            selected,
        )
    except sqlite3.Error:
        logger.exception("SQLite error while resolving poll answer poll_id=%s", poll_id)
        return

    if status != "ok" or updated is None:
        if status not in {"missing_poll", "stale_poll"}:
            logger.info("Ignoring poll answer poll_id=%s status=%s", poll_id, status)
        return

    chat_id = int(updated["user_id"])
    await continue_quiz_or_finish(context, updated, chat_id)
