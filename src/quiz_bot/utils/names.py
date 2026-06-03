"""Name helpers."""

from __future__ import annotations

import sqlite3


def user_display_name(row: sqlite3.Row) -> str:
    username = row["username"]
    full_name = row["full_name"]
    if username:
        return f"@{username}"
    if full_name:
        return str(full_name)
    return "Unknown"
