"""Telegram API helpers."""

from __future__ import annotations

import logging

from telegram.error import BadRequest, Conflict, NetworkError, TelegramError

logger = logging.getLogger(__name__)


def is_message_not_modified(error: BaseException) -> bool:
    return isinstance(error, BadRequest) and "message is not modified" in str(error).lower()


def is_polling_error(update: object) -> bool:
    return update is None


def is_recoverable_polling_error(error: BaseException) -> bool:
    return isinstance(error, NetworkError)


async def safe_edit_message_text(
    query,
    text: str,
    *,
    parse_mode: str | None = None,
    reply_markup=None,
    unchanged_hint: str | None = None,
) -> bool:
    try:
        await query.edit_message_text(
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        return True
    except BadRequest as exc:
        if is_message_not_modified(exc):
            if unchanged_hint:
                await query.answer(unchanged_hint, show_alert=False)
            else:
                await query.answer()
            return True
        logger.exception("BadRequest while editing message")
        return False
    except TelegramError:
        logger.exception("Telegram error while editing message")
        return False
