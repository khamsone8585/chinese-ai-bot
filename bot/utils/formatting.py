"""
bot/utils/formatting.py
───────────────────────
Telegram HTML formatting helpers for translation and chat output.

Why HTML over MarkdownV2?
  - HTML escaping is simpler and more predictable.
  - MarkdownV2 requires escaping many characters that appear naturally
    in Chinese/Thai text (parentheses, dashes, dots, etc.).
"""

import html


def _esc(text: str) -> str:
    """Escape a string for Telegram HTML parse mode."""
    return html.escape(str(text))


def _level_block(emoji: str, label_th: str, level: dict) -> str:
    """Render a single formality-level block including the Thai back-translation."""
    chinese = _esc(level.get("chinese", "—"))
    pinyin = _esc(level.get("pinyin", "—"))
    thai_tr = _esc(level.get("thai_translation", ""))

    lines = [
        f"{emoji} <b>{label_th}</b>",
        f"🇨🇳 <b>{chinese}</b>",
        f"📖 <i>{pinyin}</i>",
    ]
    if thai_tr:
        lines.append(f"🇹🇭 แปลไทย: {thai_tr}")

    return "\n".join(lines)


def format_th_to_cn(result: dict, original: str) -> str:
    """
    Format a Thai→Chinese multi-level translation result for Telegram (HTML).

    Args:
        result: dict with keys 'formal', 'semi_formal', 'chat', 'close_friend'
                (each {"chinese", "pinyin", "thai_translation"})
                and 'vocabulary' (list of {"word", "pinyin", "meaning"})
        original: The user's original Thai input text — displayed at the top.

    Returns:
        HTML-formatted string ready for Telegram.
    """
    original_esc = _esc(original)

    # ── Header: original Thai ─────────────────────────────────────────────────
    lines = [f"🇹🇭 <i>{original_esc}</i>", ""]

    # ── Formality levels ──────────────────────────────────────────────────────
    levels = [
        ("🏢", "ประโยคทางการ (Formal)",                "formal"),
        ("💼", "ประโยคกึ่งทางการ (Semi-formal)",        "semi_formal"),
        ("📱", "ประโยคพิมพ์แชท (Chat)",                 "chat"),
        ("🍻", "ประโยคคุยกับเพื่อนสนิท (Close Friend)", "close_friend"),
    ]

    for emoji, label, key in levels:
        level_data = result.get(key, {})
        if level_data:
            lines.append(_level_block(emoji, label, level_data))
            lines.append("")   # blank line between sections

    # ── Vocabulary list ───────────────────────────────────────────────────────
    vocab: list = result.get("vocabulary", [])
    if vocab:
        lines.append("💡 <b>คำศัพท์ที่ต้องรู้ (Vocabulary)</b>")
        for item in vocab:
            word    = _esc(item.get("word", ""))
            pinyin  = _esc(item.get("pinyin", ""))
            meaning = _esc(item.get("meaning", ""))
            if word:
                lines.append(f"• {word} <i>({pinyin})</i> — {meaning}")

    return "\n".join(lines).rstrip()


def format_cn_to_th(result: dict, original: str) -> str:
    """
    Format a Chinese→Thai translation result for Telegram (HTML).

    Args:
        result: dict with 'thai', 'note' keys from translator.py
        original: The user's original Chinese input text

    Returns:
        HTML-formatted string ready for Telegram.
    """
    thai = _esc(result.get("thai", "—"))
    note = _esc(result.get("note", ""))
    original_esc = _esc(original)

    lines = [
        f"🇨🇳 <i>{original_esc}</i>",
        "",
        f"🇹🇭 <b>{thai}</b>",
    ]

    if note:
        lines.append(f"💡 <i>{note}</i>")

    return "\n".join(lines)


def format_error(message: str) -> str:
    """Format an error message for Telegram."""
    return f"⚠️ {_esc(message)}"
