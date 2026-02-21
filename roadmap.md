# 🤖 Personal Chinese-Thai AI Assistant — Roadmap

> A private Telegram bot for **Thai ↔ Chinese translation** (with Pinyin) and **Chinese conversation practice**, secured by a user-ID whitelist.

---

## 1. Optimal Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| **Language** | Python 3.11+ | Mature async ecosystem, excellent library support |
| **Telegram Library** | [`python-telegram-bot`](https://github.com/python-telegram-bot/python-telegram-bot) v21+ | Async-first, actively maintained, clean `ConversationHandler` for multi-mode flows |
| **LLM API** | **Claude API (Anthropic)** — primary recommendation | Superior multilingual nuance for CJK languages; excellent instruction-following for structured output (translation + pinyin). Falls back gracefully into natural conversation mode |
| **LLM Alternative** | OpenAI `gpt-4o` | Strong Chinese capability; useful as a fallback or for cost comparison |
| **Pinyin** | LLM-generated inline | Claude/GPT can produce accurate pinyin alongside translations — no extra library needed for the MVP |
| **Config & Secrets** | `python-dotenv` + `.env` file | Simple, secure secret management |
| **Logging** | Python `logging` (stdlib) | Zero-dependency, production-ready |
| **Deployment** | VPS (e.g., DigitalOcean / AWS Lightsail) or Railway | Long-running polling process; cheap $5-6/mo VPS is sufficient |

### Why Claude over OpenAI for this use case?

1. **Chinese linguistic accuracy** — Claude handles tonal nuance, measure words (量词), and colloquial Thai-Chinese mapping very well.
2. **Structured output** — Easy to instruct "return JSON with `translation`, `pinyin`, `literal`" fields.
3. **Conversation persona** — Claude excels at maintaining a consistent "native Chinese speaker" personality across a long chat session.

> [!TIP]
> You can support **both** APIs behind a simple adapter and switch via `.env` config. The plan below accounts for this.

---

## 2. Recommended Folder Structure

```
chinese_ai_bot/
├── .env                     # Secrets (TELEGRAM_TOKEN, ANTHROPIC_API_KEY, ALLOWED_USER_IDS)
├── .env.example             # Template with placeholder values (committed to git)
├── .gitignore
├── requirements.txt
├── README.md
├── roadmap.md               # ← this file
│
├── bot/
│   ├── __init__.py
│   ├── main.py              # Entry point — sets up Application & handlers
│   ├── config.py            # Loads .env, exposes settings dataclass
│   ├── handlers/
│   │   ├── __init__.py
│   │   ├── start.py         # /start, /help commands
│   │   ├── translate.py     # /th2cn, /cn2th & inline translation logic
│   │   ├── chat.py          # /chat, /endchat — conversation-partner mode
│   │   └── common.py        # Shared error handler, unknown-command handler
│   ├── middlewares/
│   │   ├── __init__.py
│   │   └── auth.py          # Whitelist check decorator / middleware
│   ├── services/
│   │   ├── __init__.py
│   │   ├── llm_client.py    # Thin wrapper around Anthropic SDK (swappable)
│   │   ├── translator.py    # Prompt engineering for translation + pinyin
│   │   └── chat_partner.py  # Prompt engineering for conversation mode
│   └── utils/
│       ├── __init__.py
│       └── formatting.py    # Telegram markdown/HTML formatting helpers
│
└── tests/
    ├── __init__.py
    ├── test_auth.py
    ├── test_translator.py
    └── test_chat_partner.py
```

### Key design decisions

- **`handlers/`** — One file per user-facing feature. Keeps command registration clean.
- **`services/`** — Pure business logic with no Telegram dependency → easy to unit-test.
- **`middlewares/auth.py`** — Single decorator `@whitelist_only` wraps every handler. A denied user gets a silent ignore or a polite rejection.
- **`llm_client.py`** — Abstract the API call so switching from Claude to OpenAI requires changing only this file + the `.env` key.

---

## 3. Step-by-Step Implementation Plan

### Phase 1 — Foundation & Security 🔐

**Goal:** Bot starts, responds to `/start`, and rejects unauthorized users.

| Step | Detail |
|---|---|
| 1.1 | Create project scaffold (folders, `.env.example`, `requirements.txt`, `.gitignore`) |
| 1.2 | Implement `config.py` — load `TELEGRAM_TOKEN`, `ANTHROPIC_API_KEY`, `ALLOWED_USER_IDS` from `.env` |
| 1.3 | Implement `middlewares/auth.py` — `@whitelist_only` decorator that checks `update.effective_user.id` against the allowed set |
| 1.4 | Implement `handlers/start.py` — `/start` and `/help` commands (wrapped with `@whitelist_only`) |
| 1.5 | Implement `main.py` — wire up the `Application`, register handlers, start polling |
| 1.6 | **Verify:** Bot responds to your user ID, silently ignores others |

> [!IMPORTANT]
> Phase 1 must be fully working before moving on. The whitelist is the security boundary — get it right first.

---

### Phase 2 — Translation Engine 🌐

**Goal:** Thai → Chinese (with Pinyin) and Chinese → Thai translation work reliably.

| Step | Detail |
|---|---|
| 2.1 | Implement `services/llm_client.py` — async wrapper around `anthropic.AsyncAnthropic` with retry + timeout |
| 2.2 | Implement `services/translator.py` — two prompt templates: `th_to_cn()` and `cn_to_th()`. The Thai→Chinese prompt must instruct the LLM to return: **Chinese characters + Pinyin + optional literal breakdown** |
| 2.3 | Implement `utils/formatting.py` — format the LLM response into clean Telegram HTML (bold Chinese, italic Pinyin) |
| 2.4 | Implement `handlers/translate.py` — `/th2cn <text>` and `/cn2th <text>` commands, plus auto-detect mode for plain messages |
| 2.5 | **Verify:** Send Thai text → receive Chinese + Pinyin; send Chinese text → receive Thai |

**Example output for `/th2cn สวัสดีครับ วันนี้อากาศดีมาก`:**

```
🇨🇳 你好！今天天气很好。
📖 Nǐ hǎo! Jīntiān tiānqì hěn hǎo.
💡 Literal: Hello! Today weather very good.
```

---

### Phase 3 — Conversation Partner 💬

**Goal:** A `/chat` mode where the bot becomes a native Chinese speaker for daily conversation practice.

| Step | Detail |
|---|---|
| 3.1 | Implement `services/chat_partner.py` — system prompt crafting a patient native Chinese speaker who replies in Chinese (with Pinyin), gently corrects mistakes, and can explain in Thai when asked |
| 3.2 | Add in-memory conversation history (list of messages per user, capped at ~20 turns to manage token cost) |
| 3.3 | Implement `handlers/chat.py` — `/chat` enters conversation mode, `/endchat` exits. Use `ConversationHandler` states |
| 3.4 | Format responses: Chinese reply + Pinyin underneath; if the user made a grammar mistake, add a 📝 correction block |
| 3.5 | **Verify:** Enter `/chat`, have a multi-turn conversation, confirm context is retained, exit with `/endchat` |

**Example conversation flow:**

```
You:  /chat
Bot:  🎓 Chat mode activated! I'll be your Chinese conversation partner.
      Just type in Chinese or Thai — let's talk! Send /endchat to exit.

You:  我今天很高心
Bot:  🇨🇳 哦，你今天很开心吗？太好了！发生了什么好事？
      📖 Ó, nǐ jīntiān hěn kāixīn ma? Tài hǎo le! Fāshēng le shénme hǎo shì?

      📝 Small correction: 高心 → 高兴 (gāoxìng) or 开心 (kāixīn)
```

---

### Phase 4 — Polish & Deploy 🚀

**Goal:** Production-ready bot with graceful error handling and easy deployment.

| Step | Detail |
|---|---|
| 4.1 | Add global error handler → catch LLM API errors, rate limits; send friendly "try again" message |
| 4.2 | Add logging throughout (structured logs with user ID, command, latency) |
| 4.3 | Write unit tests for `translator.py` and `chat_partner.py` (mock the LLM client) |
| 4.4 | Add a `Dockerfile` + `docker-compose.yml` for one-command deployment |
| 4.5 | Deploy to VPS / Railway, set up `systemd` or Docker auto-restart |
| 4.6 | **Optional enhancements:** vocabulary flashcard mode, daily word of the day, voice message support via Whisper API |

---

## 4. Command Summary

| Command | Description |
|---|---|
| `/start` | Welcome message + usage instructions |
| `/help` | List available commands |
| `/th2cn <text>` | Translate Thai → Chinese (with Pinyin) |
| `/cn2th <text>` | Translate Chinese → Thai |
| `/chat` | Enter conversation-partner mode |
| `/endchat` | Exit conversation-partner mode |

---

## 5. Cost Estimate

| Item | Estimated Cost |
|---|---|
| Claude API (Haiku for translation, Sonnet for chat) | ~$1-5/month for personal use |
| VPS (DigitalOcean / Lightsail) | ~$5-6/month |
| Telegram Bot API | Free |
| **Total** | **~$6-11/month** |

> [!NOTE]
> Using Claude Haiku for simple translations and Sonnet for conversation mode keeps costs low while maintaining quality. You can configure this per-service in `llm_client.py`.
