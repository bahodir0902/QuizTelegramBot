"""Error handlers."""

from __future__ import annotations

import logging

from telegram import Update
from telegram.error import Conflict, TelegramError
from telegram.ext import ContextTypes, ConversationHandler

from quiz_bot.keyboards import admin_dashboard_keyboard
from quiz_bot.services.localization_service import language_for_user, translate
from quiz_bot.utils.telegram import (
    is_message_not_modified,
    is_polling_error,
    is_recoverable_polling_error,
)

logger = logging.getLogger(__name__)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    error = context.error
    if error is None:
        return

    if is_message_not_modified(error):
        return

    if is_polling_error(update):
        if isinstance(error, Conflict):
            logger.error(
                "Another process is already polling Telegram with this bot token. "
                "Stop duplicate instances (for example Docker plus local `python main.py`). "
                "Details: %s",
                error,
            )
            return

        if is_recoverable_polling_error(error):
            logger.warning("Transient network error while polling for updates: %s", error)
            return

        logger.warning(
            "Telegram polling error (PTB will retry automatically): %s",
            error,
            exc_info=error,
        )
        return

    if isinstance(error, TelegramError):
        logger.error(
            "Telegram error while handling an update: %s",
            error,
            exc_info=error,
        )
        return

    logger.error(
        "Unhandled error while handling an update",
        exc_info=error,
    )


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    language_code = "en"
    if update.effective_user is not None:
        language_code = await language_for_user(update.effective_user.id)
    if update.message is not None:
        await update.message.reply_text(
            translate(language_code, "cancelled"),
            reply_markup=admin_dashboard_keyboard(language_code),
        )
    return ConversationHandler.END
