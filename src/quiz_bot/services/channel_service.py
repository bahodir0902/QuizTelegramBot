"""Channel parsing and subscription helpers."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlparse

from telegram.error import TelegramError

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{5,32}$")
JOINED_STATUSES = {"creator", "administrator", "member"}


@dataclass(frozen=True)
class ParsedChannel:
    title: str
    url: str
    username: str | None


def parse_channel_reference(raw: str) -> ParsedChannel | None:
    value = raw.strip()
    if not value:
        return None
    username: str | None = None
    url: str
    if value.startswith("@"):
        candidate = value[1:]
        if not USERNAME_RE.fullmatch(candidate):
            return None
        username = candidate
        url = f"https://t.me/{candidate}"
    elif value.startswith("http://") or value.startswith("https://"):
        parsed = urlparse(value)
        if parsed.netloc.lower() not in {"t.me", "telegram.me"}:
            return None
        path = parsed.path.strip("/")
        if not path or path.startswith("+") or path.startswith("joinchat/"):
            return None
        username = path.split("/", maxsplit=1)[0]
        if not USERNAME_RE.fullmatch(username):
            return None
        url = value
    elif USERNAME_RE.fullmatch(value):
        username = value
        url = f"https://t.me/{value}"
    else:
        return None
    title = f"@{username}" if username else url
    return ParsedChannel(title=title, url=url, username=username)


async def is_user_subscribed(bot, channel, user_id: int) -> tuple[bool, str | None]:
    username = channel["username"]
    if not username:
        return False, "missing_username"
    try:
        member = await bot.get_chat_member(chat_id=f"@{username}", user_id=user_id)
    except TelegramError:
        return False, "permission"
    return getattr(member, "status", "") in JOINED_STATUSES, None
