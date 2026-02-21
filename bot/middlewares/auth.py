"""
bot/middlewares/auth.py
───────────────────────
Whitelist-based authentication decorator.

Usage:
    @whitelist_only
    async def my_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        ...

Per .claudemd rules: EVERY handler must be wrapped with @whitelist_only.
Unauthorized users are silently ignored (no response, no error leak).
"""

import logging
from functools import wraps
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes

from bot.config import settings

logger = logging.getLogger(__name__)


def whitelist_only(func: Callable) -> Callable:
    """
    Async decorator that restricts handler access to whitelisted users only.

    - Allowed users: handler executes normally.
    - Unauthorized users: silently ignored (no reply sent).
    """

    @wraps(func)
    async def wrapper(
        update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any
    ) -> Any:
        user = update.effective_user

        # Guard: no user attached to this update (e.g. channel posts)
        if user is None:
            logger.warning("Received update with no effective_user — ignoring.")
            return

        if user.id not in settings.allowed_user_ids:
            logger.warning(
                "Unauthorized access attempt by user_id=%s username=%s",
                user.id,
                user.username,
            )
            # Silent ignore — do NOT send any message to the unauthorized user
            return

        return await func(update, context, *args, **kwargs)

    return wrapper
