"""Poll scoring service."""

from __future__ import annotations

import logging

from quiz_bot.database import adb_run, score_poll_answer_db

logger = logging.getLogger(__name__)


async def score_poll_answer(poll_id: str, answer_user_id: int, selected_option_id: int):
    updated, status = await adb_run(
        lambda conn: score_poll_answer_db(
            conn,
            poll_id,
            answer_user_id,
            selected_option_id,
        ),
        commit=True,
        immediate=True,
    )
    if status == "user_mismatch":
        logger.warning(
            "Poll answer user mismatch answer_user_id=%s poll_id=%s",
            answer_user_id,
            poll_id,
        )
    return updated, status
