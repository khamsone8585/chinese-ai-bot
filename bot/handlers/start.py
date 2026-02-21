"""
bot/handlers/start.py
─────────────────────
Handles /start and /help commands.

Per .claudemd rules:
  - Both handlers are async.
  - Both are protected by @whitelist_only.
  - No business logic here — routing only.
"""

import logging

from telegram import Update
from telegram.ext import ContextTypes

from bot.middlewares.auth import whitelist_only

logger = logging.getLogger(__name__)

HELP_TEXT = """
🤖 *Chinese\\-Thai AI Assistant*

*Available Commands:*
/start — Show this welcome message
/help — Show available commands

*Coming soon:*
/th2cn \\<text\\> — Translate Thai → Chinese \\(with Pinyin\\)
/cn2th \\<text\\> — Translate Chinese → Thai
/chat — Enter conversation\\-partner mode with a native Chinese speaker
/endchat — Exit conversation mode
""".strip()


@whitelist_only
async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to the /start command."""
    user = update.effective_user
    logger.info("User %s triggered /start", user.id if user else "unknown")

    welcome = (
        f"你好！ 👋 *Welcome, {user.first_name}\\!*\n\n"
        "I'm your personal *Chinese\\-Thai AI Assistant*\\.\n\n"
        "Here's what I can do:\n"
        "🌐 Translate between Thai and Chinese \\(with Pinyin\\)\n"
        "💬 Act as a native Chinese conversation partner\n\n"
        "Use /help to see all commands\\."
    )

    await update.message.reply_text(welcome, parse_mode="MarkdownV2")


@whitelist_only
async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Respond to the /help command."""
    user = update.effective_user
    logger.info("User %s triggered /help", user.id if user else "unknown")

    await update.message.reply_text(HELP_TEXT, parse_mode="MarkdownV2")
