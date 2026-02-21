"""
bot/services/llm_client.py
──────────────────────────
Async wrapper around the Groq API (groq Python SDK).

Design goals:
  - Single place to swap model or provider.
  - All calls are async via AsyncGroq.
  - OpenAI-compatible message format (system + user roles).
  - Clean, typed error surfacing upward.
  - No Telegram imports — pure service layer (per .claudemd architecture rules).

SDK pattern:
    from groq import AsyncGroq

    client = AsyncGroq(api_key="...")
    response = await client.chat.completions.create(
        model="llama3-70b-8192",
        messages=[
            {"role": "system", "content": "..."},
            {"role": "user",   "content": "..."},
        ],
        temperature=0.2,
        max_tokens=2048,
    )
    text = response.choices[0].message.content
"""

import logging

import groq
from groq import AsyncGroq

from bot.config import settings

logger = logging.getLogger(__name__)

# llama-3.3-70b-versatile: Groq's current flagship — excellent multilingual quality,
# 128k-token context, and generous free-tier RPM.
GROQ_MODEL = "llama-3.3-70b-versatile"

# Lazy-initialised module-level client (created once, reused across calls)
_client: AsyncGroq | None = None


def _get_client() -> AsyncGroq:
    """Return the module-level Groq async client, creating it on first call."""
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
    return _client


async def call_llm(
    *,
    system_prompt: str,
    user_message: str,
    conversation_history: list[dict] | None = None,
    temperature: float = 0.2,
    max_tokens: int = 2048,
) -> str:
    """
    Send a message to the Groq LLM and return the text response.

    Args:
        system_prompt: System instruction that shapes the model's behaviour.
        user_message: The user's input text.
        conversation_history: Optional prior turns for multi-turn chat.
                              Format: [{"role": "user"|"assistant", "content": "..."}]
        temperature: Sampling temperature (lower = more deterministic).
        max_tokens: Maximum tokens in the response.

    Returns:
        The model's reply as a plain string.

    Raises:
        RuntimeError: On any Groq API failure, with a user-friendly message.
    """
    client = _get_client()

    # Build the messages list (OpenAI-compatible format)
    messages: list[dict] = [{"role": "system", "content": system_prompt}]
    if conversation_history:
        messages.extend(conversation_history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        text = response.choices[0].message.content or ""
        if not text.strip():
            raise RuntimeError("🤖 The AI returned an empty response. Please try again.")
        logger.info("Groq raw response (%d chars): %s", len(text), text)
        return text.strip()

    except groq.AuthenticationError:
        logger.error("Groq authentication failed — check GROQ_API_KEY in .env")
        raise RuntimeError("❌ API authentication failed. Check GROQ_API_KEY in .env.")
    except groq.RateLimitError:
        logger.warning("Groq rate limit hit")
        raise RuntimeError("⏳ Rate limit reached. Please wait a moment and try again.")
    except groq.APIConnectionError as e:
        logger.error("Groq connection error: %s", e)
        raise RuntimeError("🔌 Could not connect to the AI service. Please try again.")
    except groq.APIStatusError as e:
        logger.error("Groq API status error (status=%s): %s", e.status_code, e)
        raise RuntimeError(f"🤖 AI service error ({e.status_code}). Please try again.")
    except Exception as e:
        logger.error("Unexpected error calling Groq: %s", e)
        raise RuntimeError(f"🤖 Unexpected error: {e}")
