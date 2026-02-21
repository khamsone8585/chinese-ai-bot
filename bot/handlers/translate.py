"""
bot/handlers/translate.py
─────────────────────────
Handles translation commands and auto-detection of Thai/Chinese input.

Commands:
  /th2cn <text>  — Explicitly translate Thai → Chinese (with Pinyin)
  /cn2th <text>  — Explicitly translate Chinese → Thai

Auto-detect handler:
  Plain messages (no command) are inspected character-by-character:
    - Contains CJK characters  → treated as Chinese → translate to Thai
    - Contains Thai characters  → treated as Thai → translate to Chinese

Per .claudemd rules:
  - All handlers are async.
  - All handlers are wrapped with @whitelist_only.
  - No direct API calls here — delegates entirely to bot/services/translator.py.
"""

import logging
import unicodedata

from telegram import Update
from telegram.ext import ContextTypes

from bot.middlewares.auth import whitelist_only
from bot.services.translator import translate_thai_to_chinese, translate_chinese_to_thai
from bot.utils.formatting import format_th_to_cn, format_cn_to_th, format_error

logger = logging.getLogger(__name__)


# ── Language Detection Helpers ─────────────────────────────────────────────────

def _contains_thai(text: str) -> bool:
    """Return True if the text contains at least one Thai Unicode character."""
    return any("\u0e00" <= ch <= "\u0e7f" for ch in text)


def _contains_chinese(text: str) -> bool:
    """Return True if the text contains at least one CJK Unified Ideograph."""
    return any(
        unicodedata.category(ch) in ("Lo",) and "\u4e00" <= ch <= "\u9fff"
        or "\u3400" <= ch <= "\u4dbf"  # CJK Extension A
        or "\u20000" <= ch <= "\u2a6df"  # CJK Extension B
        for ch in text
    )


def _extract_arg(update: Update, context: ContextTypes.DEFAULT_TYPE) -> str | None:
    """
    Extract the text argument from a command like /th2cn <text>.
    Returns None and sends a usage hint if no argument is provided.
    """
    if context.args:
        return " ".join(context.args).strip()
    return None


# ── Command: /th2cn ────────────────────────────────────────────────────────────

@whitelist_only
async def th2cn_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/th2cn <text> — Translate Thai → Chinese with Pinyin."""
    text = _extract_arg(update, context)
    if not text:
        await update.message.reply_text(
            "📝 Usage: /th2cn <text>\n\nExample: /th2cn สวัสดีครับ",
            parse_mode="HTML",
        )
        return

    logger.info("User %s requested TH→CN translation", update.effective_user.id)
    await _do_th_to_cn(update, text)


# ── Command: /cn2th ────────────────────────────────────────────────────────────

@whitelist_only
async def cn2th_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/cn2th <text> — Translate Chinese → Thai."""
    text = _extract_arg(update, context)
    if not text:
        await update.message.reply_text(
            "📝 Usage: /cn2th <text>\n\nExample: /cn2th 你好，今天天气怎么样？",
            parse_mode="HTML",
        )
        return

    logger.info("User %s requested CN→TH translation", update.effective_user.id)
    await _do_cn_to_th(update, text)


# ── Auto-detect Handler (plain messages) ───────────────────────────────────────

@whitelist_only
async def auto_translate_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Automatically detect whether the message is Thai or Chinese and translate it.
    Ignores messages that are neither Thai nor Chinese (e.g. pure English/emoji).
    """
    text = update.message.text or ""
    if not text.strip():
        return

    if _contains_thai(text):
        logger.info(
            "User %s auto-detected Thai input → CN translation",
            update.effective_user.id,
        )
        await _do_th_to_cn(update, text)
    elif _contains_chinese(text):
        logger.info(
            "User %s auto-detected Chinese input → TH translation",
            update.effective_user.id,
        )
        await _do_cn_to_th(update, text)
    else:
        # Non-Thai, non-Chinese input — give a helpful hint
        await update.message.reply_text(
            "🤔 ไม่รู้จะแปลอะไรดี / 不知道要翻译什么\n\n"
            "Send Thai text → I'll translate to Chinese 🇨🇳\n"
            "Send Chinese text → I'll translate to Thai 🇹🇭\n\n"
            "Or use /th2cn and /cn2th explicitly.",
            parse_mode="HTML",
        )


# ── Shared Translation Logic ──────────────────────────────────────────────────

async def _do_th_to_cn(update: Update, text: str) -> None:
    """Run Thai→Chinese translation and reply with formatted output."""
    # Show a typing indicator while Claude is working
    await update.message.chat.send_action("typing")
    try:
        result = await translate_thai_to_chinese(text)
        reply = format_th_to_cn(result, text)
        await update.message.reply_text(reply, parse_mode="HTML")
    except RuntimeError as e:
        await update.message.reply_text(format_error(str(e)), parse_mode="HTML")


async def _do_cn_to_th(update: Update, text: str) -> None:
    """Run Chinese→Thai translation and reply with formatted output."""
    await update.message.chat.send_action("typing")
    try:
        result = await translate_chinese_to_thai(text)
        reply = format_cn_to_th(result, text)
        await update.message.reply_text(reply, parse_mode="HTML")
    except RuntimeError as e:
        await update.message.reply_text(format_error(str(e)), parse_mode="HTML")
