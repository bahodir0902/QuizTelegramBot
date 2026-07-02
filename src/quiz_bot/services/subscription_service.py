"""Subscription preflight checks for gated quiz starts."""

from __future__ import annotations

import time
from dataclasses import dataclass

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from quiz_bot.config import AppSettings
from quiz_bot.services.localization_service import translate

CHECK_SUBSCRIPTION_CALLBACK = "subscription:check"
PENDING_START_TEST_INTENT = "start_test_after_subscription"
_PENDING_INTENT_KEY = "pending_quiz_intent"
_PENDING_INTENT_EXPIRES_AT_KEY = "pending_quiz_intent_expires_at"
PENDING_INTENT_TTL_SECONDS = 10 * 60
_ALLOWED_MEMBER_STATUSES = frozenset({"creator", "administrator", "member"})


@dataclass(frozen=True)
class SubscriptionPreflightResult:
    allowed: bool
    required_channels: tuple[str, ...] = tuple()


def _settings(context: ContextTypes.DEFAULT_TYPE) -> AppSettings | None:
    application = getattr(context, "application", None)
    if application is None:
        return None
    settings = application.bot_data.get("settings")
    return settings if isinstance(settings, AppSettings) else None


def required_channels(context: ContextTypes.DEFAULT_TYPE) -> tuple[str, ...]:
    settings = _settings(context)
    return settings.required_channel_ids if settings is not None else tuple()


async def check_quiz_start_subscription(
    context: ContextTypes.DEFAULT_TYPE,
    user_id: int,
) -> SubscriptionPreflightResult:
    channels = required_channels(context)
    if not channels:
        return SubscriptionPreflightResult(allowed=True)

    missing: list[str] = []
    for channel_id in channels:
        try:
            member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        except TelegramError:
            missing.append(channel_id)
            continue
        if getattr(member, "status", None) not in _ALLOWED_MEMBER_STATUSES:
            missing.append(channel_id)

    return SubscriptionPreflightResult(allowed=not missing, required_channels=tuple(missing))


def store_pending_start_test_intent(context: ContextTypes.DEFAULT_TYPE) -> None:
    context.user_data[_PENDING_INTENT_KEY] = PENDING_START_TEST_INTENT
    context.user_data[_PENDING_INTENT_EXPIRES_AT_KEY] = time.monotonic() + PENDING_INTENT_TTL_SECONDS


def pop_pending_start_test_intent(context: ContextTypes.DEFAULT_TYPE) -> bool:
    intent = context.user_data.get(_PENDING_INTENT_KEY)
    expires_at = float(context.user_data.get(_PENDING_INTENT_EXPIRES_AT_KEY, 0))
    context.user_data.pop(_PENDING_INTENT_KEY, None)
    context.user_data.pop(_PENDING_INTENT_EXPIRES_AT_KEY, None)
    return intent == PENDING_START_TEST_INTENT and time.monotonic() <= expires_at


def subscription_required_keyboard(language_code: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(translate(language_code, "check_subscription_button"), callback_data=CHECK_SUBSCRIPTION_CALLBACK)]]
    )
