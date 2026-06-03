"""Poll timeout scheduling."""

from __future__ import annotations

import asyncio
import logging

from telegram.ext import ContextTypes

from quiz_bot.database import adb_run, advance_timeout_poll_db

logger = logging.getLogger(__name__)

_TIMEOUT_TASKS_KEY = "poll_timeout_tasks"


def _timeout_tasks(context: ContextTypes.DEFAULT_TYPE) -> dict[str, asyncio.Task]:
    return context.application.bot_data.setdefault(_TIMEOUT_TASKS_KEY, {})


def cancel_poll_timeout(poll_id: str, context: ContextTypes.DEFAULT_TYPE) -> None:
    task = _timeout_tasks(context).pop(poll_id, None)
    if task is not None and not task.done():
        task.cancel()


def schedule_poll_timeout(
    context: ContextTypes.DEFAULT_TYPE,
    *,
    user_id: int,
    chat_id: int,
    poll_id: str,
    open_period: int,
) -> None:
    if open_period <= 0:
        return

    cancel_poll_timeout(poll_id, context)

    async def _watch() -> None:
        try:
            await asyncio.sleep(open_period + 1)
            updated, status = await adb_run(
                lambda conn: advance_timeout_poll_db(conn, poll_id, user_id),
                commit=True,
                immediate=True,
            )
            if status != "ok" or updated is None:
                return
            from quiz_bot.services.quiz_progress import continue_quiz_or_finish

            await continue_quiz_or_finish(context, updated, chat_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception(
                "Poll timeout handler failed user_id=%s poll_id=%s",
                user_id,
                poll_id,
            )
        finally:
            _timeout_tasks(context).pop(poll_id, None)

    _timeout_tasks(context)[poll_id] = asyncio.create_task(
        _watch(),
        name=f"poll-timeout-{poll_id}",
    )
