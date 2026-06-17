"""Application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_ABOUT_US_TEXT = (
    "About this bot:\n\n"
    "This quiz bot was created to deliver engaging educational quizzes. "
    "Edit ABOUT_US_TEXT in your environment to customize this section."
)


@dataclass(frozen=True)
class AppSettings:
    bot_token: str
    initial_admin_ids: tuple[int, ...]
    data_dir: Path
    db_path: Path
    log_level: str
    default_language: str
    db_busy_timeout_ms: int
    connect_timeout: float
    read_timeout: float
    write_timeout: float
    pool_timeout: float
    about_us_text: str


def _load_dotenv() -> None:
    dotenv_path = os.getenv("DOTENV_PATH", "").strip()
    if dotenv_path:
        path = Path(dotenv_path)
        if path.is_file():
            load_dotenv(path)
        return

    default_path = Path.cwd() / ".env"
    if default_path.is_file():
        load_dotenv(default_path)


def _parse_admin_ids(raw: str) -> tuple[int, ...]:
    values: list[int] = []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        values.append(int(part))
    return tuple(values)


def load_settings() -> AppSettings:
    """Load application settings from environment."""
    _load_dotenv()
    token = (
        os.getenv("TG_BOT_TOKEN", "").strip()
        or os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        or os.getenv("BOT_TOKEN", "").strip()
    )
    if not token:
        raise SystemExit("Set TG_BOT_TOKEN, TELEGRAM_BOT_TOKEN, or BOT_TOKEN.")

    data_dir_raw = os.getenv("QUIZ_BOT_DATA_DIR", "").strip()
    data_dir = Path(data_dir_raw) if data_dir_raw else Path.cwd()
    data_dir.mkdir(parents=True, exist_ok=True)

    raw_admin_ids = os.getenv("INITIAL_ADMIN_IDS", "").strip()
    admin_ids = _parse_admin_ids(raw_admin_ids) if raw_admin_ids else tuple()

    default_language = os.getenv("DEFAULT_LANGUAGE", "en").strip().lower() or "en"

    return AppSettings(
        bot_token=token,
        initial_admin_ids=admin_ids,
        data_dir=data_dir,
        db_path=data_dir / "quiz_bot.db",
        log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        default_language=default_language,
        db_busy_timeout_ms=int(os.getenv("DB_BUSY_TIMEOUT_MS", "5000")),
        connect_timeout=float(os.getenv("TG_CONNECT_TIMEOUT", "10")),
        read_timeout=float(os.getenv("TG_READ_TIMEOUT", "35")),
        write_timeout=float(os.getenv("TG_WRITE_TIMEOUT", "30")),
        pool_timeout=float(os.getenv("TG_POOL_TIMEOUT", "10")),
        about_us_text=os.getenv("ABOUT_US_TEXT", DEFAULT_ABOUT_US_TEXT).strip()
        or DEFAULT_ABOUT_US_TEXT,
    )
