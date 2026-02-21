"""
bot/config.py
─────────────
Single source of truth for all configuration.
Loads environment variables from .env via python-dotenv.
"""

import os
from dataclasses import dataclass, field
from dotenv import load_dotenv

# Load .env file (does nothing if it doesn't exist — useful in production
# where variables are injected by the environment directly)
load_dotenv()


def _parse_allowed_ids() -> set[int]:
    """Parse ALLOWED_USER_IDS from a comma-separated string into a set of ints."""
    raw: str = os.getenv("ALLOWED_USER_IDS", "")
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if part:
            try:
                ids.add(int(part))
            except ValueError:
                raise ValueError(
                    f"Invalid Telegram user ID in ALLOWED_USER_IDS: '{part}'. "
                    "Must be a comma-separated list of integers."
                )
    if not ids:
        raise ValueError(
            "ALLOWED_USER_IDS is empty or not set. "
            "Set at least one Telegram user ID in your .env file."
        )
    return ids


@dataclass(frozen=True)
class Settings:
    telegram_token: str
    groq_api_key: str
    allowed_user_ids: set[int] = field(default_factory=set)


def _load_settings() -> Settings:
    token = os.getenv("TELEGRAM_TOKEN", "")
    groq_key = os.getenv("GROQ_API_KEY", "")

    if not token:
        raise ValueError("TELEGRAM_TOKEN is not set in .env")
    if not groq_key:
        raise ValueError("GROQ_API_KEY is not set in .env")

    return Settings(
        telegram_token=token,
        groq_api_key=groq_key,
        allowed_user_ids=_parse_allowed_ids(),
    )


# Module-level singleton — imported throughout the project
settings: Settings = _load_settings()
