"""
bot/main.py
───────────
Entry point for the Chinese-Thai AI Assistant Telegram bot.

Responsibilities:
  - Configure logging
  - Build the Application using python-telegram-bot
  - Register all command handlers
  - Start long-polling
"""

import logging

from telegram.ext import Application, CommandHandler, ConversationHandler, MessageHandler, filters

from bot.config import settings
from bot.handlers.start import start_handler, help_handler
from bot.handlers.translate import th2cn_handler, cn2th_handler, auto_translate_handler
from bot.handlers.chat import build_chat_conversation_handler


def setup_logging() -> None:
    """Configure structured logging for the bot."""
    logging.basicConfig(
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        level=logging.INFO,
    )
    # Suppress overly verbose logs from httpx (used internally by ptb)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def build_application() -> Application:
    """Construct and configure the Telegram Application."""
    app = (
        Application.builder()
        .token(settings.telegram_token)
        .build()
    )

    # ── Command Handlers ──────────────────────────────────────────────────────
    # NOTE: Per .claudemd rules, every handler MUST use @whitelist_only.
    #       The decorators are applied inside each handler module.
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))

    # ── Phase 2: Translation Handlers ─────────────────────────────────────────
    app.add_handler(CommandHandler("th2cn", th2cn_handler))
    app.add_handler(CommandHandler("cn2th", cn2th_handler))

    # ── Phase 3: Conversation Partner ─────────────────────────────────────────
    # IMPORTANT: ConversationHandler must be registered BEFORE the auto-translate
    # MessageHandler. When the user is in CHATTING state, ptb routes the message
    # to this handler; auto_translate_handler never fires during chat mode.
    app.add_handler(build_chat_conversation_handler())

    # Auto-detect: fires on plain text messages (not commands) OUTSIDE chat mode
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, auto_translate_handler))

    return app


def main() -> None:
    """Start the bot."""
    setup_logging()
    logger = logging.getLogger(__name__)

    logger.info("Starting Chinese-Thai AI Assistant bot...")
    logger.info(
        "Whitelist contains %d user(s): %s",
        len(settings.allowed_user_ids),
        settings.allowed_user_ids,
    )

    app = build_application()

    logger.info("Bot is running. Press Ctrl+C to stop.")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
