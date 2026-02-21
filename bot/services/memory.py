"""
bot/services/memory.py
──────────────────────
Simple in-memory conversation history store per user.

Design:
  - A plain dict maps user_id (int) → list of {"role": ..., "content": ...} dicts.
  - Maximum MAX_HISTORY_MESSAGES entries are kept (sliding window, oldest dropped first).
  - This is intentionally NOT persisted — history is lost on bot restart, which is
    acceptable for a personal assistant and avoids any database dependency at this phase.

Thread safety:
  - python-telegram-bot dispatches all updates through an asyncio event loop on a single
    thread, so this plain dict is safe without locks.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Maximum number of user+assistant message pairs to retain.
# Each "turn" = 1 user msg + 1 assistant reply = 2 entries.
# 10 entries ≈ 5 full turns of context, which covers normal conversation well
# without pushing token limits.
MAX_HISTORY_MESSAGES = 10

# { user_id: [ {"role": "user"|"assistant", "content": str}, ... ] }
conversation_history: dict[int, list[dict[str, str]]] = {}


def get_history(user_id: int) -> list[dict[str, str]]:
    """Return the stored conversation history for *user_id* (may be empty list)."""
    return conversation_history.get(user_id, [])


def append_message(user_id: int, role: str, content: str) -> None:
    """
    Append a single message to the user's history, then trim to MAX_HISTORY_MESSAGES.

    Args:
        user_id: Telegram user ID.
        role:    "user" or "assistant".
        content: The message text.
    """
    if user_id not in conversation_history:
        conversation_history[user_id] = []

    conversation_history[user_id].append({"role": role, "content": content})

    # Trim oldest entries when the cap is exceeded
    if len(conversation_history[user_id]) > MAX_HISTORY_MESSAGES:
        overflow = len(conversation_history[user_id]) - MAX_HISTORY_MESSAGES
        conversation_history[user_id] = conversation_history[user_id][overflow:]
        logger.debug(
            "Trimmed %d old message(s) from history for user_id=%s", overflow, user_id
        )


def clear_history(user_id: int) -> None:
    """Delete all stored history for *user_id* (called when the user exits chat mode)."""
    if user_id in conversation_history:
        del conversation_history[user_id]
        logger.info("Cleared conversation history for user_id=%s", user_id)


def history_length(user_id: int) -> int:
    """Return the number of messages currently stored for *user_id*."""
    return len(conversation_history.get(user_id, []))
