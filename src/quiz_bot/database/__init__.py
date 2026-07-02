"""Database exports and compatibility helpers."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from quiz_bot.config import AppSettings, load_settings
from quiz_bot.config.settings import DEFAULT_ABOUT_US_TEXT
from quiz_bot.database.connection import connect
from quiz_bot.database.migrations import apply_migrations
from quiz_bot.database.repositories import (
    advance_timeout_poll_db,
    build_question_pool_db,
    clear_active_poll_db,
    complete_onboarding_db,
    complete_quiz_session_db,
    count_questions_db,
    delete_question_db,
    delete_question_option_db,
    fetch_export_rows_db,
    fetch_leaderboard_db,
    fetch_question_db,
    fetch_question_stats_db,
    get_user_by_poll_id_db,
    get_user_progress_db,
    increment_score_and_advance_db,
    insert_question_db,
    is_admin_user,
    list_questions_db,
    mark_session_status_db,
    read_config,
    replace_question_options_db,
    load_profile_db,
    mark_profile_completed_db,
    save_quiz_pool_db,
    save_onboarding_age_db,
    save_onboarding_name_db,
    save_profile_full_name_db,
    save_profile_phone_number_db,
    save_profile_study_or_address_db,
    update_profile_from_my_info_db,
    score_poll_answer_db,
    seed_admin_db,
    set_user_language_db,
    set_onboarding_step_db,
    toggle_config_field_db,
    update_config_field_db,
    update_question_correct_index_db,
    update_question_text_db,
    update_poll_state_db,
    upsert_user_db,
)
from quiz_bot.database.transactions import adb_run as _adb_run
from quiz_bot.database.transactions import db_run as _db_run
from quiz_bot.domain import BotConfig, QuizStartError

logger = logging.getLogger(__name__)

_settings_override: AppSettings | None = None
DB_PATH: Path | None = None


def _compat_settings() -> AppSettings:
    global _settings_override
    if DB_PATH is not None:
        base = _settings_override
        if base is None:
            try:
                base = load_settings()
            except SystemExit:
                base = AppSettings(
                    bot_token="TEST_TOKEN",
                    initial_admin_ids=tuple(),
                    data_dir=DB_PATH.parent,
                    db_path=DB_PATH,
                    log_level="INFO",
                    default_language="en",
                    db_busy_timeout_ms=5000,
                    connect_timeout=10.0,
                    read_timeout=30.0,
                    write_timeout=30.0,
                    pool_timeout=10.0,
                    about_us_text=DEFAULT_ABOUT_US_TEXT,
                )
        return AppSettings(
            bot_token=base.bot_token,
            initial_admin_ids=base.initial_admin_ids,
            data_dir=DB_PATH.parent,
            db_path=DB_PATH,
            log_level=base.log_level,
            default_language=base.default_language,
            db_busy_timeout_ms=base.db_busy_timeout_ms,
            connect_timeout=base.connect_timeout,
            read_timeout=base.read_timeout,
            write_timeout=base.write_timeout,
            pool_timeout=base.pool_timeout,
            about_us_text=base.about_us_text,
        )

    if _settings_override is not None:
        return _settings_override

    try:
        return load_settings()
    except SystemExit:
        fallback_dir = Path.cwd()
        return AppSettings(
            bot_token="TEST_TOKEN",
            initial_admin_ids=tuple(),
            data_dir=fallback_dir,
            db_path=fallback_dir / "quiz_bot.db",
            log_level="INFO",
            default_language="en",
            db_busy_timeout_ms=5000,
            connect_timeout=10.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=10.0,
            about_us_text=DEFAULT_ABOUT_US_TEXT,
        )


def configure_database_settings(settings: AppSettings) -> None:
    global _settings_override, DB_PATH
    _settings_override = settings
    DB_PATH = settings.db_path


def _connect() -> sqlite3.Connection:
    return connect(_compat_settings())


def init_database(settings: AppSettings | None = None) -> None:
    active = settings or _compat_settings()
    configure_database_settings(active)
    conn: sqlite3.Connection | None = None
    try:
        conn = connect(active)
        apply_migrations(conn)
        conn.commit()
        logger.info("Database initialized at %s", active.db_path)
    except sqlite3.Error:
        logger.exception("Failed to initialize database")
        raise
    finally:
        if conn is not None:
            conn.close()


def seed_initial_admins(settings: AppSettings | None = None) -> None:
    active = settings or _compat_settings()
    if not active.initial_admin_ids:
        logger.info("No initial admin IDs configured")
        return
    conn: sqlite3.Connection | None = None
    try:
        conn = connect(active)
        for user_id in active.initial_admin_ids:
            seed_admin_db(conn, user_id)
        conn.commit()
        logger.info("Seeded %d admin(s)", len(active.initial_admin_ids))
    except sqlite3.Error:
        logger.exception("Failed to seed admins")
        raise
    finally:
        if conn is not None:
            conn.close()


def db_run(fn, *, commit: bool = False, immediate: bool = False):
    return _db_run(_compat_settings(), fn, commit=commit, immediate=immediate)


async def adb_run(fn, *, commit: bool = False, immediate: bool = False):
    return await _adb_run(_compat_settings(), fn, commit=commit, immediate=immediate)


def start_quiz_session_db(conn: sqlite3.Connection, user_id: int) -> list[int]:
    if count_questions_db(conn) == 0:
        raise QuizStartError("NO_QUESTIONS")
    config = read_config(conn)
    pool = build_question_pool_db(conn, config)
    if not pool:
        raise QuizStartError("EMPTY_POOL")
    save_quiz_pool_db(conn, user_id, pool)
    return pool


__all__ = [
    "BotConfig",
    "DB_PATH",
    "QuizStartError",
    "_connect",
    "adb_run",
    "advance_timeout_poll_db",
    "build_question_pool_db",
    "clear_active_poll_db",
    "complete_onboarding_db",
    "complete_quiz_session_db",
    "configure_database_settings",
    "count_questions_db",
    "delete_question_db",
    "delete_question_option_db",
    "db_run",
    "fetch_export_rows_db",
    "fetch_leaderboard_db",
    "fetch_question_db",
    "fetch_question_stats_db",
    "get_user_by_poll_id_db",
    "get_user_progress_db",
    "increment_score_and_advance_db",
    "init_database",
    "insert_question_db",
    "is_admin_user",
    "list_questions_db",
    "mark_session_status_db",
    "read_config",
    "replace_question_options_db",
    "load_profile_db",
    "mark_profile_completed_db",
    "save_quiz_pool_db",
    "save_onboarding_age_db",
    "save_onboarding_name_db",
    "save_profile_full_name_db",
    "save_profile_phone_number_db",
    "save_profile_study_or_address_db",
    "update_profile_from_my_info_db",
    "score_poll_answer_db",
    "seed_initial_admins",
    "set_user_language_db",
    "set_onboarding_step_db",
    "start_quiz_session_db",
    "toggle_config_field_db",
    "update_config_field_db",
    "update_question_correct_index_db",
    "update_question_text_db",
    "update_poll_state_db",
    "upsert_user_db",
]
