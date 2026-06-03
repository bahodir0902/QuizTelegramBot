"""Process entrypoint for the quiz bot."""

from __future__ import annotations

from telegram import Update

from quiz_bot.app import build_application
from quiz_bot.config import configure_logging, load_settings
from quiz_bot.database import init_database, seed_initial_admins


def main() -> None:
    """Run the bot process."""
    settings = load_settings()
    configure_logging(settings)
    init_database(settings)
    seed_initial_admins(settings)

    application = build_application(settings)
    application.run_polling(
        allowed_updates=Update.ALL_TYPES,
        drop_pending_updates=True,
    )


if __name__ == "__main__":
    main()
