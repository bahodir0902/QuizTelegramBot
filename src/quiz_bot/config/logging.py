"""Logging bootstrap with token masking."""

from __future__ import annotations

import logging
import re

from quiz_bot.config.settings import AppSettings


class SensitiveDataFilter(logging.Filter):
    """Mask secrets in log messages without breaking non-string format args."""

    def __init__(self, bot_token: str) -> None:
        super().__init__()
        escaped_token = re.escape(bot_token)
        self._patterns = [
            (re.compile(escaped_token), "***TG_BOT_TOKEN***"),
            (
                re.compile(r"https://api\.telegram\.org/bot[^/\s]+"),
                "https://api.telegram.org/bot***TG_BOT_TOKEN***",
            ),
            (
                re.compile(r"\b\d{8,12}:[A-Za-z0-9_-]{20,}\b"),
                "***TG_BOT_TOKEN***",
            ),
        ]

    def _mask(self, value: str) -> str:
        masked = value
        for pattern, replacement in self._patterns:
            masked = pattern.sub(replacement, masked)
        return masked

    def _mask_arg(self, arg: object) -> object:
        if isinstance(arg, str):
            return self._mask(arg)
        return arg

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = self._mask(str(record.msg))
        if record.args:
            record.args = tuple(self._mask_arg(arg) for arg in record.args)
        return True


def configure_logging(settings: AppSettings) -> None:
    """Configure root logging."""
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(getattr(logging, settings.log_level, logging.INFO))

    handler = logging.StreamHandler()
    handler.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    )
    handler.addFilter(SensitiveDataFilter(settings.bot_token))
    root.addHandler(handler)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.INFO)
