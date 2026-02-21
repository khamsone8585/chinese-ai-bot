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


# ── Conversation Partner ───────────────────────────────────────────────────────

# System prompt that turns the model into a patient native-Chinese conversation
# partner who replies in Chinese, adds Pinyin, and gives a short Thai translation.
CHAT_SYSTEM_PROMPT = """
You are 小明 (Xiǎo Míng), a friendly native Chinese speaker living in Bangkok.
Your role is to help Thai people practise conversational Mandarin Chinese.

Reply rules — follow these EVERY turn without exception:
1. Reply naturally in Chinese first (simplified characters).
2. On the next line, write the full Pinyin transcription of your Chinese reply.
3. On the next line, write a short Thai translation so the user understands.
4. If the user made a Chinese grammar or vocabulary mistake, add a gentle correction
   block at the end starting with "📝 แก้ไข:" followed by the corrected phrase and
   a brief explanation in Thai.
5. End your reply with ONE engaging follow-up question (in Chinese) to keep the
   conversation going. Then add its Pinyin and Thai translation too.
6. Keep your replies concise — 2–4 sentences of Chinese per turn is ideal.
7. If the user writes in Thai, understand it and reply as described above.
8. Be warm, encouraging, and patient. Never criticise — always praise effort.

Output format example:
---
你好！很高兴认识你。你今天好吗？
Nǐ hǎo! Hěn gāoxìng rènshi nǐ. Nǐ jīntiān hǎo ma?
สวัสดี! ยินดีที่ได้รู้จัก วันนี้เป็นยังไงบ้าง?
---
Never break character. Never explain the format itself.
""".strip()


async def chat_with_ai(user_id: int, text: str) -> str:
    """
    Send *text* to the Groq LLM as part of an ongoing conversation for *user_id*.

    This function:
      1. Reads the user's stored history from memory.py.
      2. Appends the new user message to history.
      3. Calls the LLM with the full history as context.
      4. Appends the assistant reply to history.
      5. Returns the reply string.

    The caller does NOT need to manage history — this function is the single
    entry point for all chat interactions.

    Args:
        user_id: Telegram user ID (used as history key).
        text:    The user's message text.

    Returns:
        The assistant's reply as a plain string.

    Raises:
        RuntimeError: Propagated from call_llm() on any API failure.
    """
    # Import here to avoid a circular import at module load time
    from bot.services.memory import get_history, append_message

    # 1. Fetch existing history (may be empty on first turn)
    history = get_history(user_id)

    # 2. Persist the user's new message BEFORE calling the LLM so that even if
    #    the call fails the message is recorded for next time.
    append_message(user_id, "user", text)

    # 3. Call LLM with the full history as context
    logger.info(
        "Calling Groq chat for user_id=%s | history_len=%d | input=%r",
        user_id,
        len(history),
        text[:80],
    )
    reply = await call_llm(
        system_prompt=CHAT_SYSTEM_PROMPT,
        user_message=text,
        conversation_history=history,   # history BEFORE the current message
        temperature=0.75,               # Higher temperature → more natural, varied chat
        max_tokens=1024,
    )

    # 4. Persist the assistant's reply
    append_message(user_id, "assistant", reply)

    return reply
