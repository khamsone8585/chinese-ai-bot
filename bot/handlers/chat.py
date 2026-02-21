"""
bot/handlers/chat.py
────────────────────
Conversation-partner mode — Phase 3.

Flow:
  User sends /chat → bot enters CHATTING state and greets the user.
  User sends any text → bot replies via chat_with_ai() (contexts remembered).
  User sends /endchat → bot exits the conversation, clears history.

Implementation:
  Uses python-telegram-bot's ConversationHandler which maps states to handlers.
  This approach is cleaner than a manual flag approach because:
    - State is managed by ptb's built-in machinery (no global dict needed for mode).
    - The CHATTING state filters messages so other global handlers (auto_translate)
      do NOT fire during a chat session — no cross-mode interference.
    - Fallbacks ensure /endchat works even if the user sends it in any state.

States:
  CHATTING  — waiting for the user's next chat message.

Per .claudemd rules:
  - All handlers are async.
  - All handlers are wrapped with @whitelist_only.
  - No direct API calls here — delegates entirely to bot/services/llm_client.py.
"""

import logging

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.middlewares.auth import whitelist_only
from bot.services.llm_client import chat_with_ai
from bot.services.memory import clear_history, history_length

logger = logging.getLogger(__name__)

# ── ConversationHandler state constant ────────────────────────────────────────
CHATTING = 1


# ── /chat — Entry point ───────────────────────────────────────────────────────

@whitelist_only
async def chat_start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    /chat — Activate conversation-partner mode.

    Greets the user and transitions into the CHATTING state.
    Any previously saved history is preserved so users can resume a session.
    """
    user = update.effective_user
    logger.info("User %s entered /chat mode", user.id)

    turns = history_length(user.id) // 2  # rough turn count
    resume_note = (
        f"\n\n_(เรายังจำบทสนทนาก่อนหน้าได้ {turns} เทิร์น)_" if turns > 0 else ""
    )

    greeting = (
        "🎓 <b>เปิดโหมดสนทนาภาษาจีนแล้ว!</b>\n\n"
        "สวัสดี！我是小明 (Xiǎo Míng) นะ 👋\n"
        "พิมพ์ภาษาไทยหรือภาษาจีนก็ได้ — เราจะคุยกันได้เลย！\n\n"
        "📌 พิมพ์ <code>/endchat</code> เพื่อออกจากโหมดนี้"
        f"{resume_note}"
    )

    await update.message.reply_text(greeting, parse_mode="HTML")
    return CHATTING


# ── CHATTING state — message handler ──────────────────────────────────────────

@whitelist_only
async def chat_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Handle every plain-text message while in CHATTING state.

    Sends the message to the LLM (with full conversation history) and replies.
    Stays in CHATTING state after each turn.
    """
    user = update.effective_user
    text = (update.message.text or "").strip()

    if not text:
        return CHATTING  # ignore empty messages

    logger.info(
        "Chat message from user_id=%s | history_len=%d | text=%r",
        user.id,
        history_length(user.id),
        text[:80],
    )

    # Show typing indicator while the LLM is working
    await update.message.chat.send_action("typing")

    try:
        reply = await chat_with_ai(user.id, text)
        await update.message.reply_text(reply, parse_mode=None)  # plain text — AI formats it
    except RuntimeError as e:
        error_msg = (
            f"⚠️ {e}\n\n"
            "_กรุณาลองพิมพ์ใหม่อีกครั้ง หรือพิมพ์ /endchat เพื่อออก_"
        )
        await update.message.reply_text(error_msg, parse_mode="Markdown")

    return CHATTING  # stay in chat mode


# ── /endchat — Exit handler ───────────────────────────────────────────────────

@whitelist_only
async def chat_end_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    /endchat — Deactivate conversation-partner mode and clear history.

    Clears the stored conversation history so the next /chat session starts fresh.
    Returns ConversationHandler.END to signal that the conversation is over.
    """
    user = update.effective_user
    logger.info("User %s exited /chat mode", user.id)

    turns = history_length(user.id) // 2
    clear_history(user.id)

    farewell = (
        "👋 <b>ออกจากโหมดสนทนาแล้ว</b>\n\n"
        f"เราคุยกันไปทั้งหมด {turns} เทิร์น 🎉\n"
        "ประวัติการสนทนาถูกล้างแล้ว — ครั้งหน้าเราเริ่มใหม่ได้เลย!\n\n"
        "พิมพ์ /chat เพื่อเริ่มใหม่ หรือใช้ /th2cn, /cn2th เพื่อแปลภาษา 🌐"
    )

    await update.message.reply_text(farewell, parse_mode="HTML")
    return ConversationHandler.END


# ── ConversationHandler factory ───────────────────────────────────────────────

def build_chat_conversation_handler() -> ConversationHandler:
    """
    Construct and return the fully configured ConversationHandler for chat mode.

    Registered in main.py BEFORE the auto-translate MessageHandler so that
    messages sent during a chat session are captured by this handler and do
    NOT reach auto_translate_handler.
    """
    return ConversationHandler(
        entry_points=[
            CommandHandler("chat", chat_start_handler),
        ],
        states={
            CHATTING: [
                # Capture every non-command text message while in chat mode
                MessageHandler(filters.TEXT & ~filters.COMMAND, chat_message_handler),
            ],
        },
        fallbacks=[
            # /endchat works from any state
            CommandHandler("endchat", chat_end_handler),
        ],
        # Allow the user to also use /endchat when not in chat mode (returns END safely)
        allow_reentry=True,
        # Do not persist state across bot restarts (in-memory only, consistent with memory.py)
        persistent=False,
        # Use per-user state (each user has their own conversation state)
        per_user=True,
        per_chat=False,
    )
