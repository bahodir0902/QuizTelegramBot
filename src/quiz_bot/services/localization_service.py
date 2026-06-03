"""Localization helpers."""

from __future__ import annotations

from quiz_bot.locales.messages import MESSAGES


def resolve_language(language_code: str | None, default: str = "en") -> str:
    candidate = (language_code or "").strip().lower()
    if candidate in MESSAGES:
        return candidate
    return default if default in MESSAGES else "en"


def translate(language_code: str, key: str, **kwargs: object) -> str:
    lang = resolve_language(language_code)
    template = MESSAGES.get(lang, MESSAGES["en"])[key]
    return template.format(**kwargs)


async def language_for_user(user_id: int) -> str:
    from quiz_bot.database import adb_run, get_user_progress_db

    row = await adb_run(lambda conn: get_user_progress_db(conn, user_id))
    return resolve_language(row["language_code"] if row else "en")
