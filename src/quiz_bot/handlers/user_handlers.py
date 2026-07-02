"""User-facing handlers."""

from __future__ import annotations

import logging
import sqlite3

from telegram import ReplyKeyboardRemove, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes, ConversationHandler

from quiz_bot.config import ASK_ONBOARD_AGE, ASK_ONBOARD_FULL_NAME, ASK_ONBOARD_REGION
from quiz_bot.config.settings import DEFAULT_ABOUT_US_TEXT
from quiz_bot.database import (
    adb_run,
    complete_onboarding_db,
    get_user_progress_db,
    is_admin_user,
    save_onboarding_age_db,
    save_onboarding_name_db,
    set_onboarding_step_db,
    start_quiz_session_db,
    upsert_user_db,
)
from quiz_bot.domain import QuizStartError
from quiz_bot.keyboards import (
    language_keyboard,
    main_reply_keyboard,
    region_reply_keyboard,
)
from quiz_bot.locales.messages import (
    ABOUT_US_LABELS,
    ADMIN_DASHBOARD_LABELS,
    CHANGE_LANGUAGE_LABELS,
    START_QUIZ_LABELS,
)
from quiz_bot.services.localization_service import resolve_language, translate
from quiz_bot.services.onboarding_service import (
    is_onboarding_complete,
    next_onboarding_state,
    parse_age,
    parse_full_name,
    parse_region,
    state_to_step,
)
from quiz_bot.services.quiz_service import serve_question

logger = logging.getLogger(__name__)

MENU_LABELS = frozenset(
    (*START_QUIZ_LABELS, *CHANGE_LANGUAGE_LABELS, *ABOUT_US_LABELS, *ADMIN_DASHBOARD_LABELS)
)


def _telegram_full_name(user) -> str:
    return user.full_name or user.first_name or "User"


def _progress_language(progress) -> str:
    return resolve_language(progress["language_code"] if progress else "en")


async def _ensure_user_progress(update: Update):
    user = update.effective_user
    if user is None:
        return None
    await adb_run(
        lambda conn: upsert_user_db(
            conn,
            user.id,
            user.username,
            _telegram_full_name(user),
        ),
        commit=True,
    )
    return await adb_run(lambda conn: get_user_progress_db(conn, user.id))


async def _send_language_prompt(update: Update) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        translate("en", "language_prompt"),
        reply_markup=language_keyboard(),
    )


async def _is_admin(user_id: int) -> bool:
    return await adb_run(lambda conn: is_admin_user(conn, user_id))


async def _send_welcome(
    update: Update, language_code: str, *, is_admin: bool = False
) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        translate(
            language_code,
            "welcome",
            start_quiz_label=translate(language_code, "start_quiz_label"),
        ),
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=main_reply_keyboard(language_code, is_admin=is_admin),
    )


async def _send_next_step_after_onboarding(update: Update, progress) -> int:
    language_code = _progress_language(progress)
    if progress["language_code"] in (None, ""):
        await _send_language_prompt(update)
        return ConversationHandler.END
    is_admin = False
    if update.effective_user is not None:
        is_admin = await _is_admin(update.effective_user.id)
    await _send_welcome(update, language_code, is_admin=is_admin)
    return ConversationHandler.END


async def _prompt_onboarding_step(update: Update, progress) -> int:
    if update.message is None or update.effective_user is None:
        return ConversationHandler.END

    state = next_onboarding_state(progress)
    if state == ConversationHandler.END:
        return ConversationHandler.END

    language_code = _progress_language(progress)
    await adb_run(
        lambda conn: set_onboarding_step_db(
            conn,
            update.effective_user.id,
            state_to_step(state),
        ),
        commit=True,
    )

    if state == ASK_ONBOARD_AGE:
        await update.message.reply_text(
            translate(language_code, "onboarding_age_prompt"),
            reply_markup=ReplyKeyboardRemove(),
        )
        return ASK_ONBOARD_AGE

    if state == ASK_ONBOARD_REGION:
        await update.message.reply_text(
            translate(language_code, "onboarding_region_prompt"),
            reply_markup=region_reply_keyboard(),
        )
        return ASK_ONBOARD_REGION

    await update.message.reply_text(
        translate(language_code, "onboarding_name_prompt"),
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_ONBOARD_FULL_NAME


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    if update.effective_user is None:
        return ConversationHandler.END

    try:
        progress = await _ensure_user_progress(update)
    except sqlite3.Error:
        logger.exception(
            "SQLite error during /start registration user_id=%s",
            update.effective_user.id,
        )
        if update.message is not None:
            await update.message.reply_text(translate("en", "db_error"))
        return ConversationHandler.END

    if progress is None:
        return ConversationHandler.END

    if not is_onboarding_complete(progress):
        return await _prompt_onboarding_step(update, progress)

    return await _send_next_step_after_onboarding(update, progress)


async def handle_onboarding_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    raw = update.message.text or ""
    try:
        progress = await adb_run(
            lambda conn: get_user_progress_db(conn, update.effective_user.id)
        )
    except sqlite3.Error:
        logger.exception(
            "SQLite error while loading onboarding name user_id=%s",
            update.effective_user.id,
        )
        await update.message.reply_text(translate("en", "db_error"))
        return ConversationHandler.END
    language_code = _progress_language(progress)
    parsed = None if raw.strip() in MENU_LABELS else parse_full_name(raw)
    if parsed is None:
        await update.message.reply_text(
            translate(language_code, "onboarding_name_invalid")
        )
        return ASK_ONBOARD_FULL_NAME

    first_name, last_name = parsed
    try:
        await adb_run(
            lambda conn: save_onboarding_name_db(
                conn,
                update.effective_user.id,
                first_name,
                last_name,
            ),
            commit=True,
        )
    except sqlite3.Error:
        logger.exception(
            "SQLite error while saving onboarding name user_id=%s",
            update.effective_user.id,
        )
        await update.message.reply_text(translate(language_code, "db_error"))
        return ConversationHandler.END

    await update.message.reply_text(
        translate(language_code, "onboarding_age_prompt"),
        reply_markup=ReplyKeyboardRemove(),
    )
    return ASK_ONBOARD_AGE


async def handle_onboarding_age(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    try:
        progress = await adb_run(
            lambda conn: get_user_progress_db(conn, update.effective_user.id)
        )
    except sqlite3.Error:
        logger.exception(
            "SQLite error while loading onboarding age user_id=%s",
            update.effective_user.id,
        )
        await update.message.reply_text(translate("en", "db_error"))
        return ConversationHandler.END
    language_code = _progress_language(progress)
    age = parse_age(update.message.text)
    if age is None:
        await update.message.reply_text(
            translate(language_code, "onboarding_age_invalid")
        )
        return ASK_ONBOARD_AGE

    try:
        await adb_run(
            lambda conn: save_onboarding_age_db(conn, update.effective_user.id, age),
            commit=True,
        )
    except sqlite3.Error:
        logger.exception(
            "SQLite error while saving onboarding age user_id=%s",
            update.effective_user.id,
        )
        await update.message.reply_text(translate(language_code, "db_error"))
        return ConversationHandler.END

    await update.message.reply_text(
        translate(language_code, "onboarding_region_prompt"),
        reply_markup=region_reply_keyboard(),
    )
    return ASK_ONBOARD_REGION


async def handle_onboarding_region(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    del context
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    try:
        progress = await adb_run(
            lambda conn: get_user_progress_db(conn, update.effective_user.id)
        )
    except sqlite3.Error:
        logger.exception(
            "SQLite error while loading onboarding region user_id=%s",
            update.effective_user.id,
        )
        await update.message.reply_text(translate("en", "db_error"))
        return ConversationHandler.END
    language_code = _progress_language(progress)
    raw = update.message.text or ""
    region = None if raw.strip() in MENU_LABELS else parse_region(raw)
    if region is None:
        await update.message.reply_text(
            translate(language_code, "onboarding_region_invalid")
        )
        return ASK_ONBOARD_REGION

    try:
        updated = await adb_run(
            lambda conn: complete_onboarding_db(conn, update.effective_user.id, region),
            commit=True,
        )
    except sqlite3.Error:
        logger.exception(
            "SQLite error while completing onboarding user_id=%s",
            update.effective_user.id,
        )
        await update.message.reply_text(translate(language_code, "db_error"))
        return ConversationHandler.END

    await update.message.reply_text(
        translate(language_code, "onboarding_complete"),
        reply_markup=ReplyKeyboardRemove(),
    )
    return await _send_next_step_after_onboarding(update, updated)


async def handle_start_quiz(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id if update.effective_chat else user_id

    try:
        progress = await _ensure_user_progress(update)
    except sqlite3.Error:
        logger.exception("SQLite error while ensuring quiz user user_id=%s", user_id)
        await update.message.reply_text(translate("en", "db_error"))
        return ConversationHandler.END

    language_code = _progress_language(progress)
    if progress is None:
        await update.message.reply_text(translate(language_code, "send_start_first"))
        return ConversationHandler.END

    if not is_onboarding_complete(progress):
        await update.message.reply_text(
            translate(language_code, "complete_registration_first")
        )
        return await _prompt_onboarding_step(update, progress)

    if progress["language_code"] in (None, ""):
        await _send_language_prompt(update)
        return ConversationHandler.END

    try:
        pool = await adb_run(
            lambda conn: start_quiz_session_db(conn, user_id),
            commit=True,
            immediate=True,
        )
    except QuizStartError as exc:
        message_key = "no_questions" if str(exc) == "NO_QUESTIONS" else "empty_pool"
        await update.message.reply_text(translate(language_code, message_key))
        return ConversationHandler.END
    except sqlite3.Error:
        logger.exception("SQLite error while starting quiz user_id=%s", user_id)
        await update.message.reply_text(translate(language_code, "db_error"))
        return ConversationHandler.END

    await update.message.reply_text(
        translate(language_code, "quiz_started", count=len(pool)),
        reply_markup=main_reply_keyboard(language_code, is_admin=await _is_admin(user_id)),
    )
    await serve_question(context, user_id, chat_id)
    return ConversationHandler.END


async def handle_about_us(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if update.effective_user is None or update.message is None:
        return ConversationHandler.END

    try:
        progress = await _ensure_user_progress(update)
    except sqlite3.Error:
        logger.exception(
            "SQLite error while opening About Us user_id=%s",
            update.effective_user.id,
        )
        await update.message.reply_text(translate("en", "db_error"))
        return ConversationHandler.END

    language_code = _progress_language(progress)
    if progress is None:
        await update.message.reply_text(translate(language_code, "send_start_first"))
        return ConversationHandler.END

    if not is_onboarding_complete(progress):
        await update.message.reply_text(
            translate(language_code, "complete_registration_first")
        )
        return await _prompt_onboarding_step(update, progress)

    application = getattr(context, "application", None)
    settings = application.bot_data.get("settings") if application else None
    about_text = getattr(settings, "about_us_text", DEFAULT_ABOUT_US_TEXT)
    await update.message.reply_text(
        about_text,
        reply_markup=main_reply_keyboard(
            language_code, is_admin=await _is_admin(update.effective_user.id)
        ),
    )
    return ConversationHandler.END
