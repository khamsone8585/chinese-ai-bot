# 🇨🇳🇹🇭 Chinese-Thai AI Assistant Bot (Telegram)

A highly responsive and context-aware Telegram Bot designed to act as a personal Chinese language tutor and conversation partner. Powered by the blazing-fast **Groq API (Llama 3.3)**, this bot goes beyond simple translation by deeply understanding Thai conversational nuances and delivering localized Chinese outputs.

## ✨ Core Features

### 1. 🧠 Smart Translation Engine (4-Level Formality)
Unlike standard translators, this bot analyzes the emotional intent and conversational context of the Thai input to generate four distinct levels of Chinese translation:
* 🏢 **Formal (ทางการ):** Suitable for business and professional settings.
* 💼 **Semi-formal (กึ่งทางการ):** Polite everyday communication.
* 📱 **Chat (พิมพ์แชท):** Natural text-messaging style.
* 🍻 **Close Friend (เพื่อนสนิท):** Highly colloquial with appropriate slang.
* *Includes accurate Pinyin, detailed Thai literal translations, and a vocabulary breakdown for each request.*

### 2. 💬 AI Conversation Partner (Phase 3)
A built-in `/chat` mode that maintains conversation history in-memory. It acts as a native Chinese speaker, allowing users to practice real-time conversational Chinese with context-aware responses and follow-up questions.

### 3. 🔒 Robust Security (Whitelist System)
Implemented a custom `@whitelist_only` decorator middleware to ensure the bot responds strictly to authorized Telegram User IDs, preventing unauthorized access and protecting API usage quotas.

## 🛠️ Tech Stack & Architecture
* **Language:** Python 3.x
* **LLM Provider:** Groq API (`llama-3.3-70b-versatile` for ultra-fast, low-latency inference)
* **Framework:** `python-telegram-bot` (Asynchronous handling)
* **Architecture:** Modular design separating Handlers, Services (LLM client, Memory, Translator), and Utilities (Formatting, Auth).

## 🚀 Key Technical Highlights
* **Advanced Prompt Engineering:** Specifically tuned to handle Thai language nuances, such as omitted subjects/objects (e.g., translating "ไม่รักกันแล้ว" correctly based on 1st/2nd person context) and colloquial misspellings (e.g., "ทำมั้ย" -> 为什么).
* **Resilient JSON Parsing:** Custom regex-based extraction to ensure the Telegram formatter always receives clean, valid JSON from the LLM, preventing crash loops.

## ⚙️ How to Run Locally

1. Clone the repository:
   ```bash
   git clone [https://github.com/YOUR_USERNAME/chinese-ai-bot.git](https://github.com/YOUR_USERNAME/chinese-ai-bot.git)
   cd chinese-ai-bot
