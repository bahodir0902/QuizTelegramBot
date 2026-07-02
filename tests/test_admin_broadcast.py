"""Admin broadcast flow tests."""

from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from telegram.error import Forbidden
from telegram.ext import ConversationHandler

from quiz_bot.config.constants import (
    ASK_BROADCAST_CONFIRM,
    ASK_BROADCAST_TEXT,
    CB_ADMIN_BROADCAST,
    CB_BROADCAST_CANCEL,
    CB_BROADCAST_SEND,
)
from quiz_bot.handlers import admin_handlers


class DummyMessage:
    def __init__(self, text: str = "") -> None:
        self.text = text
        self.replies: list[dict[str, object]] = []
        self.chat_id = 999

    async def reply_text(self, text: str, **kwargs: object) -> None:
        self.replies.append({"text": text, **kwargs})


class DummyQuery:
    def __init__(self, data: str) -> None:
        self.data = data
        self.message = SimpleNamespace(chat_id=999)
        self.answers: list[tuple[tuple[object, ...], dict[str, object]]] = []
        self.edits: list[dict[str, object]] = []

    async def answer(self, *args: object, **kwargs: object) -> None:
        self.answers.append((args, kwargs))

    async def edit_message_text(self, **kwargs: object) -> None:
        self.edits.append(kwargs)


class DummyContext:
    def __init__(self) -> None:
        self.user_data: dict[str, object] = {}
        self.bot = SimpleNamespace(send_message=AsyncMock())


def message_update(user_id: int, text: str) -> SimpleNamespace:
    return SimpleNamespace(effective_user=SimpleNamespace(id=user_id), message=DummyMessage(text))


def callback_update(user_id: int, data: str) -> SimpleNamespace:
    return SimpleNamespace(effective_user=SimpleNamespace(id=user_id), callback_query=DummyQuery(data))


async def fake_language_for_user(_user_id: int) -> str:
    return "en"


class AdminBroadcastTests(unittest.IsolatedAsyncioTestCase):
    async def test_admin_only_access_denies_non_admin_callback(self) -> None:
        async def fake_adb_run(fn, **_kwargs):
            return False

        update = callback_update(55, CB_ADMIN_BROADCAST)
        context = DummyContext()
        with patch.object(admin_handlers, "adb_run", fake_adb_run), patch.object(
            admin_handlers, "language_for_user", fake_language_for_user
        ):
            result = await admin_handlers.admin_callback_router(update, context)

        self.assertEqual(result, ConversationHandler.END)
        self.assertIn("not an administrator", update.callback_query.edits[0]["text"])

    async def test_cancel_flow_clears_pending_broadcast(self) -> None:
        async def fake_adb_run(fn, **_kwargs):
            return True

        update = callback_update(1, CB_BROADCAST_CANCEL)
        context = DummyContext()
        context.user_data["broadcast_text"] = "Hello"
        with patch.object(admin_handlers, "adb_run", fake_adb_run), patch.object(
            admin_handlers, "language_for_user", fake_language_for_user
        ):
            result = await admin_handlers.admin_broadcast_confirm(update, context)

        self.assertEqual(result, ConversationHandler.END)
        self.assertNotIn("broadcast_text", context.user_data)
        self.assertEqual(update.callback_query.edits[0]["text"], "Broadcast cancelled.")

    async def test_empty_message_rejection(self) -> None:
        async def fake_adb_run(fn, **_kwargs):
            return True

        update = message_update(1, "   ")
        context = DummyContext()
        with patch.object(admin_handlers, "adb_run", fake_adb_run), patch.object(
            admin_handlers, "language_for_user", fake_language_for_user
        ):
            result = await admin_handlers.admin_broadcast_text(update, context)

        self.assertEqual(result, ASK_BROADCAST_TEXT)
        self.assertIn("cannot be empty", update.message.replies[0]["text"])

    async def test_confirmation_stores_message_and_prompts(self) -> None:
        async def fake_adb_run(fn, **_kwargs):
            return True

        update = message_update(1, "Hello users")
        context = DummyContext()
        with patch.object(admin_handlers, "adb_run", fake_adb_run), patch.object(
            admin_handlers, "language_for_user", fake_language_for_user
        ):
            result = await admin_handlers.admin_broadcast_text(update, context)

        self.assertEqual(result, ASK_BROADCAST_CONFIRM)
        self.assertEqual(context.user_data["broadcast_text"], "Hello users")
        self.assertIn("Hello users", update.message.replies[0]["text"])

    async def test_successful_send_count(self) -> None:
        users = [{"user_id": 10}, {"user_id": 11}]

        async def fake_adb_run(fn, **_kwargs):
            if getattr(fn, "__name__", "") == "list_registered_users_db":
                return users
            return True

        update = callback_update(1, CB_BROADCAST_SEND)
        context = DummyContext()
        context.user_data["broadcast_text"] = "Hi"
        with patch.object(admin_handlers, "adb_run", fake_adb_run), patch.object(
            admin_handlers, "language_for_user", fake_language_for_user
        ):
            result = await admin_handlers.admin_broadcast_confirm(update, context)

        self.assertEqual(result, ConversationHandler.END)
        self.assertEqual(context.bot.send_message.await_count, 2)
        self.assertIn("Sent: 2. Failed: 0", update.callback_query.edits[0]["text"])

    async def test_failure_count(self) -> None:
        users = [{"user_id": 10}, {"user_id": 11}]

        async def fake_adb_run(fn, **_kwargs):
            if getattr(fn, "__name__", "") == "list_registered_users_db":
                return users
            return True

        context = DummyContext()
        context.user_data["broadcast_text"] = "Hi"
        context.bot.send_message.side_effect = [None, Forbidden("blocked")]
        update = callback_update(1, CB_BROADCAST_SEND)
        with patch.object(admin_handlers, "adb_run", fake_adb_run), patch.object(
            admin_handlers, "language_for_user", fake_language_for_user
        ):
            result = await admin_handlers.admin_broadcast_confirm(update, context)

        self.assertEqual(result, ConversationHandler.END)
        self.assertIn("Sent: 1. Failed: 1", update.callback_query.edits[0]["text"])
