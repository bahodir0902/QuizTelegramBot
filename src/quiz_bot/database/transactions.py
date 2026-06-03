"""Database execution wrappers."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from collections.abc import Callable
from typing import TypeVar

from quiz_bot.config import AppSettings
from quiz_bot.database.connection import connect

logger = logging.getLogger(__name__)

T = TypeVar("T")


def db_run(
    settings: AppSettings,
    fn: Callable[[sqlite3.Connection], T],
    *,
    commit: bool = False,
    immediate: bool = False,
) -> T:
    conn: sqlite3.Connection | None = None
    try:
        conn = connect(settings)
        if immediate:
            conn.execute("BEGIN IMMEDIATE")
        result = fn(conn)
        if commit:
            conn.commit()
        return result
    except sqlite3.Error:
        logger.exception("SQLite operation failed")
        raise
    finally:
        if conn is not None:
            conn.close()


async def adb_run(
    settings: AppSettings,
    fn: Callable[[sqlite3.Connection], T],
    *,
    commit: bool = False,
    immediate: bool = False,
) -> T:
    return await asyncio.to_thread(
        db_run,
        settings,
        fn,
        commit=commit,
        immediate=immediate,
    )
