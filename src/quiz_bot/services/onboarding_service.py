"""Onboarding validation and state helpers."""

from __future__ import annotations

from telegram.ext import ConversationHandler

from quiz_bot.config import (
    ASK_ONBOARD_AGE,
    ASK_ONBOARD_FULL_NAME,
    ASK_ONBOARD_REGION,
)

ONBOARD_STEP_FULL_NAME = "full_name"
ONBOARD_STEP_PHONE = "phone_number"
ONBOARD_STEP_STUDY = "study_or_address"


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
    if not str(row["profile_full_name"] or "").strip():
        return ASK_ONBOARD_FULL_NAME
    if not str(row["profile_phone_number"] or "").strip():
        return ASK_ONBOARD_AGE
    if not str(row["profile_study_or_address"] or "").strip():
        return ASK_ONBOARD_REGION
    return ASK_ONBOARD_REGION


def state_to_step(state: int) -> str:
    if state == ASK_ONBOARD_AGE:
        return ONBOARD_STEP_PHONE
    if state == ASK_ONBOARD_REGION:
        return ONBOARD_STEP_STUDY
    return ONBOARD_STEP_FULL_NAME


def parse_profile_full_name(raw: str | None) -> str | None:
    text = " ".join((raw or "").strip().split())
    return text or None


def parse_full_name(raw: str | None) -> tuple[str, str] | None:
    parts = [part for part in (raw or "").strip().split() if part]
    if len(parts) < 2:
        return None
    first_name = parts[0]
    last_name = " ".join(parts[1:])
    return first_name, last_name


def parse_phone_number(raw: str | None) -> str | None:
    text = " ".join((raw or "").strip().split())
    if not text:
        return None
    digits = [ch for ch in text if ch.isdigit()]
    allowed = set("+()-. ")
    if any(not (ch.isdigit() or ch in allowed) for ch in text):
        return None
    if len(digits) < 7 or len(digits) > 15:
        return None
    if "+" in text and not text.startswith("+"):
        return None
    return text


def parse_age(raw: str | None) -> int | None:
    text = (raw or "").strip()
    if not text.isdecimal():
        return None
    age = int(text)
    if age < 1 or age > 120:
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
