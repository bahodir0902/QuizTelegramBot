"""Onboarding validation and state helpers."""

from __future__ import annotations

from telegram.ext import ConversationHandler

from quiz_bot.config import (
    ASK_ONBOARD_AGE,
    ASK_ONBOARD_FULL_NAME,
    ASK_ONBOARD_REGION,
)

ONBOARD_STEP_FULL_NAME = "full_name"
ONBOARD_STEP_AGE = "age"
ONBOARD_STEP_REGION = "region"

MAX_AGE = 120


def is_onboarding_complete(row) -> bool:
    if row is None:
        return False
    try:
        return bool(int(row["onboarding_completed"]))
    except (KeyError, TypeError, ValueError):
        return False


def next_onboarding_state(row) -> int:
    if is_onboarding_complete(row):
        return ConversationHandler.END
    if row is None:
        return ASK_ONBOARD_FULL_NAME
    if not row["first_name"] or not row["last_name"]:
        return ASK_ONBOARD_FULL_NAME
    if row["age"] is None:
        return ASK_ONBOARD_AGE
    if not str(row["region"] or "").strip():
        return ASK_ONBOARD_REGION
    return ASK_ONBOARD_REGION


def state_to_step(state: int) -> str:
    if state == ASK_ONBOARD_AGE:
        return ONBOARD_STEP_AGE
    if state == ASK_ONBOARD_REGION:
        return ONBOARD_STEP_REGION
    return ONBOARD_STEP_FULL_NAME


def parse_full_name(raw: str | None) -> tuple[str, str] | None:
    parts = [part for part in (raw or "").strip().split() if part]
    if len(parts) < 2:
        return None
    first_name = parts[0]
    last_name = " ".join(parts[1:])
    return first_name, last_name


def parse_age(raw: str | None) -> int | None:
    text = (raw or "").strip()
    if not text.isdecimal():
        return None
    age = int(text)
    if age < 1 or age > MAX_AGE:
        return None
    return age


def parse_region(raw: str | None) -> str | None:
    text = " ".join((raw or "").strip().split())
    if not text:
        return None
    return text


def format_duration(seconds: int | None) -> str:
    value = max(0, int(seconds or 0))
    return f"{value} second" if value == 1 else f"{value} seconds"
