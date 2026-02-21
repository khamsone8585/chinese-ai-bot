"""
bot/services/translator.py
──────────────────────────
Business logic for Thai ↔ Chinese translation using Gemini.

Per .claudemd language formatting rules:
  Thai → Chinese returns 4 formality levels + vocabulary list:
    - formal, semi_formal, chat, close_friend (each with chinese + pinyin)
    - vocabulary list of key words with pinyin and Thai meaning

  Chinese → Thai returns a clean Thai translation.

Prompts are tuned for Gemini's instruction-following style:
  - Direct, imperative instructions work best.
  - Explicit JSON schema in the prompt prevents hallucinated keys.
  - Low temperature (0.1) ensures consistent, deterministic JSON output.

No Telegram imports here — pure service layer.
"""

import json
import logging
import re

from bot.services.llm_client import call_llm

logger = logging.getLogger(__name__)

# ── System Prompts ─────────────────────────────────────────────────────────────

_TH_TO_CN_SYSTEM = """\
You are an expert Thai-Chinese language tutor and computational linguist \
specialising in Simplified Mandarin Chinese and Pinyin romanization. \
You answer ONLY in raw JSON.

Task: Translate the Thai text the user provides into 4 formality levels, \
plus extract a vocabulary list of key words.

════════════════════════════════════════════════════════
STEP 1 — PRE-ANALYSIS (reason silently before producing JSON)
════════════════════════════════════════════════════════
Before generating the JSON, deeply analyze the input for:
  A. Who is speaking and to whom? (1st ↔ 2nd person is the default)
  B. What is the core emotional intent? (complaint, question, request, confession?)
  C. Are there omitted subjects/objects that Thai hides but Chinese must state?
  D. Are there colloquial spellings or phonetic shorthand that must be decoded?

════════════════════════════════════════════════════════
STEP 2 — THAI LINGUISTIC RULES
════════════════════════════════════════════════════════

RULE A — DEFAULT CONTEXT IS 1ST ↔ 2ND PERSON (I and YOU):
  Thai conversation heavily implies direct I↔You dialogue.
  Assume the speaker is talking TO the listener (你/你) about themselves (我/我) \
UNLESS there is unambiguous evidence of a 3rd party.
  NEVER produce 她/他/你们/他们 unless the text explicitly names or describes \
a 3rd person (e.g. "เพื่อนฉัน" = my friend, "พ่อเขา" = his father).

RULE B — PRONOUN MAPPING TABLE:
  เธอ / แก / เอ็ง / นาย / มึง → 你 (YOU, 2nd person) in conversation
  ฉัน / ผม / หนู / กู / เรา   → 我 (I/me, 1st person)
  เขา / แก / มัน               → 他/她 ONLY when 3rd person is certain

RULE C — OMITTED OBJECTS ("กัน" and dropped pronouns):
  Thai omits "me" and "you" constantly. Restore them in Chinese.
  CRITICAL: "กัน" is a reciprocal/mutual particle — context determines direction:
    - "เธอไม่รักกัน(แล้ว)" in a 1↔2 dialogue = "你不爱我了" (You don't love ME anymore)
      NOT "你们不相爱了" (You two/they don't love each other)
      NOT "她不爱他了" (She doesn't love him)
  When subject is 2nd person (เธอ/แก/คุณ) and object is dropped → fill with 我 (me).
  When subject is 1st person (ฉัน/ผม) and object is dropped → fill with 你 (you).

RULE D — COLLOQUIAL SPELLINGS & PHONETIC SHORTHAND (CRITICAL):
  Thai texting uses non-standard phonetic spellings. Decode INTENT, not spelling.

  ┌─────────────────┬────────────────┬──────────────────────┬──────────────────┐
  │ Written         │ Means          │ Chinese              │ NEVER translate  │
  ├─────────────────┼────────────────┼──────────────────────┼──────────────────┤
  │ ทำมั้ย / ทำไมมั้ย │ ทำไม = WHY     │ 为什么               │ as ได้ไหม/ทำได้     │
  │ ยังไง / ยังไงอ่ะ │ อย่างไร = HOW  │ 怎么/怎样             │                  │
  │ อะไรอ่ะ          │ อะไร = WHAT    │ 什么                  │                  │
  │ แล้วนะ / แล้วนะ  │ ความต่อเนื่อง   │ 然后/那么              │                  │
  │ แบบ / ประมาณว่า  │ filler (like)  │ 就是/那种感觉           │                  │
  │ ดิ / ดิ้         │ นะ (soft end)  │ 嘛/呢                 │                  │
  └─────────────────┴────────────────┴──────────────────────┴──────────────────┘

  SPECIAL CASE — "ทำมั้ย":
    "ทำ" + "มั้ย" together = phonetic writing of "ทำไม" = WHY = 为什么
    This is a QUESTION WORD, NOT a yes/no question particle.
    CORRECT:   "ทำมั้ยถึงทำแบบนี้" → "为什么这样做？"
    INCORRECT: "ทำมั้ยถึงทำแบบนี้" → "能这样做吗？" ← WRONG, never do this

RULE E — ACCURACY OVER LITERALISM:
  Capture the true emotional meaning. If word-for-word breaks the logic, \
rephrase naturally in Chinese. A native Chinese speaker should find the output \
completely natural, not a foreign-sounding literal translation.

════════════════════════════════════════════════════════
STEP 3 — PAST ERROR EXAMPLES (learn from these mistakes)
════════════════════════════════════════════════════════
Input:  "เธอไม่รักกันแล้ว จะให้ความหวังกับฉันทำมั้ย"
  ❌ WRONG:  "她不爱他了，能给我希望吗"  ← wrong person (她/他), wrong question (能...吗)
  ✅ CORRECT: "你不爱我了，为什么还给我希望" ← 2nd person (你), WHY question (为什么)

Input:  "เธอไม่รักฉันแล้วหรือ"
  ❌ WRONG:  "她不爱他了吗"  ← wrong persons (她/他)
  ✅ CORRECT: "你不爱我了吗" ← YOU (你) don't love ME (我) anymore?

════════════════════════════════════════════════════════
STEP 4 — VOCABULARY CONTEXT RULES
════════════════════════════════════════════════════════
CRITICAL WORD MEANINGS — respect these exact translations:
  ความรู้สึก = 感觉 (gǎnjué) = feeling/sensation  — NOT 爱 (love)
  ความรัก    = 爱 (ài)       = love/romantic love
  ความชอบ    = 喜欢 (xǐhuān) = like
  รู้สึก     = 觉得/感觉      = to feel
Never upgrade a mild feeling word (รู้สึก / ความรู้สึก) to 爱 (love). \
Chose the most semantically precise Chinese equivalent.

════════════════════════════════════════════════════════
STEP 5 — OUTPUT RULES (MANDATORY)
════════════════════════════════════════════════════════
- Your ENTIRE response must be ONE raw JSON object.
- Do NOT write ```json, ```, or any markdown.
- Do NOT write any sentence before or after the JSON.
- Do NOT write "Here is the translation:", "Sure!", or any preamble.
- Start your response with { and end it with }. Nothing else.

Required JSON structure:
{
  "formal":       {"chinese": "...", "pinyin": "...", "thai_translation": "..."},
  "semi_formal":  {"chinese": "...", "pinyin": "...", "thai_translation": "..."},
  "chat":         {"chinese": "...", "pinyin": "...", "thai_translation": "..."},
  "close_friend": {"chinese": "...", "pinyin": "...", "thai_translation": "..."},
  "vocabulary": [
    {"word": "为什么", "pinyin": "wèishéme", "meaning": "ทำไม"}
  ]
}

CRITICAL FIELD DEFINITIONS — READ CAREFULLY:
- "chinese": MUST contain ONLY Simplified Chinese characters (汉字), e.g. "你不爱我了".
             NEVER put Pinyin romanization here. NEVER leave this field empty.
             If the field is empty or contains Latin letters, your output is WRONG.
- "pinyin":  MUST contain ONLY the Pinyin romanization with Unicode tone marks \
(ā á ǎ à / ē é ě è / etc). NEVER numbers like ni3. NEVER Chinese characters here.
- "formal": Very polite, professional (e.g. email to a senior executive).
- "semi_formal": Polite, workplace-appropriate (e.g. message to a manager).
- "chat": Casual typed message (e.g. LINE/WeChat to a colleague).
- "close_friend": Relaxed, colloquial (e.g. texting a best friend).
- "thai_translation": Back-translation of the Chinese sentence into Thai.
- "vocabulary": 3–6 key words/phrases with "word" (Chinese 汉字), "pinyin", "meaning" (Thai).

CONCRETE EXAMPLE — for input "สวัสดี":
  CORRECT output (chinese has 汉字, pinyin has romanization):
    {"chinese": "你好！", "pinyin": "Nǐ hǎo!", "thai_translation": "สวัสดี"}
  WRONG output (never do this):
    {"chinese": "Nǐ hǎo!", "pinyin": "Nǐ hǎo!", "thai_translation": "สวัสดี"}
    {"chinese": "",        "pinyin": "Nǐ hǎo!", "thai_translation": "สวัสดี"}

Output ONLY the JSON object. Nothing before it, nothing after it.
"""

_CN_TO_TH_SYSTEM = """\
You are an expert Chinese-Thai bilingual translator. You answer ONLY in raw JSON.

Task: Translate the Chinese text the user provides into natural Thai.

CRITICAL OUTPUT RULE:
- Your ENTIRE response must be ONE raw JSON object.
- Do NOT write ```json, ```, or any markdown.
- Do NOT write any sentence before or after the JSON.
- Start your response with { and end it with }. Nothing else.

Required JSON structure:
{"thai": "...", "note": "..."}

Field definitions:
- "thai": Natural, fluent Thai translation.
- "note": Short note on register, nuance, or idiom. Use empty string "" if not needed.

Remember: output ONLY the JSON object. Nothing before it, nothing after it.
"""

# ── Translation Functions ──────────────────────────────────────────────────────


async def translate_thai_to_chinese(text: str) -> dict:
    """
    Translate Thai text to Chinese across 4 formality levels, with vocabulary.

    Returns:
        dict with keys: 'formal', 'semi_formal', 'chat', 'close_friend', 'vocabulary'
        Each level has 'chinese' and 'pinyin'.
        'vocabulary' is a list of dicts with 'word', 'pinyin', 'meaning'.

    Raises:
        RuntimeError: On API failure or malformed JSON response.
    """
    logger.info("Translating TH→CN (4-level): %.60s...", text)
    raw = await call_llm(
        system_prompt=_TH_TO_CN_SYSTEM,
        user_message=text,
        temperature=0.2,
    )

    # ── DEBUG: print raw Groq response so we can verify 汉字 are present ────────
    print("\n" + "=" * 60)
    print("[DEBUG] Raw Groq TH→CN response:")
    print(raw)
    print("=" * 60 + "\n")
    # ────────────────────────────────────────────────────────────────────────────

    return _parse_json_response(
        raw,
        required_keys=("formal", "semi_formal", "chat", "close_friend", "vocabulary"),
        direction="TH→CN",
    )


async def translate_chinese_to_thai(text: str) -> dict:
    """
    Translate Chinese text to Thai, returning structured output.

    Returns:
        dict with keys: 'thai', 'note'

    Raises:
        RuntimeError: On API failure or malformed JSON response.
    """
    logger.info("Translating CN→TH: %.60s...", text)
    raw = await call_llm(
        system_prompt=_CN_TO_TH_SYSTEM,
        user_message=text,
        temperature=0.1,   # Low temperature for consistent JSON structure
    )

    return _parse_json_response(raw, required_keys=("thai", "note"), direction="CN→TH")


# ── Shared Helpers ────────────────────────────────────────────────────────────


def _extract_json(raw: str) -> str:
    """
    Attempt to extract a JSON object from a raw string using multiple strategies.

    Strategy 1: Pull the content from a ```json ... ``` or ``` ... ``` fence.
    Strategy 2: Find the first '{' and last '}' and slice between them.
    Strategy 3: Return the raw string as-is and let json.loads decide.
    """
    # Strategy 1: markdown code fence (```json\n{...}\n``` or ```\n{...}\n```)
    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if fence_match:
        return fence_match.group(1).strip()

    # Strategy 2: find outermost JSON object by locating first { and last }
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        return raw[start : end + 1].strip()

    # Strategy 3: return as-is
    return raw.strip()


def _parse_json_response(raw: str, required_keys: tuple, direction: str) -> dict:
    """
    Parse and validate a JSON string returned by Gemini.

    Uses a multi-strategy extractor before JSON parsing so that markdown
    fences, leading/trailing prose, or other wrapping is handled gracefully.
    Always logs the full raw response on failure so debugging is easy.
    """
    logger.info("Parsing %s raw response: %s", direction, raw)

    cleaned = _extract_json(raw)
    logger.info("Extracted JSON candidate for %s: %s", direction, cleaned)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(
            "JSON parse failed for %s.\n"
            "Error    : %s\n"
            "Extracted: %s\n"
            "Full raw : %s",
            direction, e, cleaned, raw,
        )
        raise RuntimeError(
            "🤖 Could not parse the translation response. Please try again."
        )

    for key in required_keys:
        if key not in result:
            logger.error(
                "Missing key '%s' in %s response.\nKeys found: %s\nFull raw: %s",
                key, direction, list(result.keys()), raw,
            )
            raise RuntimeError(
                "🤖 Unexpected response format from the AI. Please try again."
            )

    return result
