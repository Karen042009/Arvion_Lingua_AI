# Arvion Lingua AI 🤖🌍
### 🏆 Developed for *Quick With Gemini Hackathon 2026*

A powerful Telegram bot for language learning, AI-powered voice chat, and translation — built on Google Gemini AI.

---

## 🚀 Hackathon Sprint Features 

During the **Quick with Gemini Hackathon**, we optimized our core interactions and added a new transparency command:
- 📊 **`/models` Command** — Real-time transparency showing the ranked priority queue of available Gemini models on the active API key and showing the dynamic self-healing status.
- 🎤 **Gemini Voice Chat** — Send voice messages, get text + voice AI responses with Gemini transcription.
- 🏆 **Smart Model Auto-Ranking** — Dynamic model exploration and fallback logic tailored for maximum uptime.

---

## Features

### 🎤 Gemini Voice Chat 

- Send a **voice message** in the Chat section and the bot will:
  1. **Transcribe** your audio to text using Gemini AI
  2. **Generate** a smart AI response
  3. **Reply with text AND voice** (TTS in your learning language)
- Works in both Regular Chat and Role-Play scenarios
- Perfect for practicing pronunciation and listening skills

### 🏆 Smart Model Auto-Ranking 
The bot dynamically fetches all models available on your API key and ranks them from best to worst:

| Priority | Model Family |
|----------|-------------|
| 1st | Gemini 3.1 Pro |
| 2nd | Gemini 3 Pro |
| 3rd | Gemini 2.5 Pro |
| 4th | Gemini 2.0 Pro / 1.5 Pro |
| 5th | Gemini 3.1 Flash |
| 6th | Gemini 3 Flash |
| 7th | Gemini 2.5 Flash / 2.0 Flash |
| ... | Other available models |

### 🔄 Automatic Fallback 

- If the top model is unavailable (quota/error), the bot **automatically tries the next best model**
- Works for all features: chat, translation, learning, transcription
- No manual intervention needed

### 🌐 Language Translation

- Translate text between 13 supported languages
- Auto-detect source language
- Swap source/target languages
- Image OCR + translation (send a photo)
- TTS pronunciation for source and translated text

### 📚 Natural Language Learning

- Adaptive levels: **A1/A2**, **B1/B2**, **C1/C2**
- Vocabulary flash cards
- AI-generated quizzes with instant feedback
- Daily streak tracking
- Progress statistics

### 💬 AI Chat & Role-Play

- **Regular Chat**: Open-ended conversation with Gemini
- **Role-Play Scenarios**:
  - ☕ At the Cafe
  - 🏨 At the Hotel
  - 💼 Job Interview
- Persistent chat history per user
- Voice message support in all chat modes

### 🎓 Programming Language Learning

- 10 programming languages: Python, JavaScript, Java, C#, C++, PHP, Swift, Kotlin, SQL, Go
- Three levels: Beginner, Intermediate, Advanced
- Concept explanations with code examples
- Interactive coding quizzes

### 🔊 Text-to-Speech

- Converts AI responses to audio using gTTS
- Multi-language audio support
- Responses voiced in your selected learning language

### 🖼️ Image Text Recognition

- Extract and translate text from photos
- AI-powered image analysis via Gemini

### ⚙️ User Settings

- Interface language (13 languages)
- Native language selection
- Learning language & level
- Programming language & level
- Learning mode (Human languages / Programming)

### 📊 Statistics & Tracking

- Translations count
- Words/concepts learned
- Quizzes passed
- Facts requested
- Daily activity streak

---

## Supported Languages

| Code | Language   | Code | Language   |
|------|-----------|------|-----------|
| en   | English   | ja   | Japanese  |
| hy   | Armenian  | ko   | Korean    |
| ru   | Russian   | hi   | Hindi     |
| es   | Spanish   | ar   | Arabic    |
| fr   | French    | de   | German    |
| it   | Italian   | pt   | Portuguese|
| zh   | Chinese   |      |           |

---

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Language | Python 3.8+ |
| Bot Framework | aiogram 3.5.0 |
| AI Engine | Google Generative AI (Gemini) |
| Database | SQLite (async via aiosqlite) |
| Text-to-Speech | gTTS 2.5.1 |
| Image Processing | Pillow 10.3.0 |

### Dependencies

```
aiogram==3.5.0
python-dotenv==1.0.1
google-generativeai==0.5.4
gTTS==2.5.1
aiosqlite==0.20.0
Pillow==10.3.0
aiohttp-socks
```

---

## Project Structure

```
Arvion_Lingua_AI/
├── main.py                 # Bot entry point & router setup
├── config.py               # Configuration and constants
├── requirements.txt        # Python dependencies
├── .env                    # Environment variables (not tracked)
├── bot/
│   ├── handlers/           # Message and callback handlers
│   │   ├── chat_handlers.py        # Chat + Voice Chat handler
│   │   ├── common_handlers.py
│   │   ├── learning_handlers.py
│   │   ├── settings_handlers.py
│   │   ├── translate_handlers.py
│   │   └── __init__.py
│   ├── keyboards/          # Telegram keyboards
│   │   ├── inline.py
│   │   ├── reply.py
│   │   └── __init__.py
│   ├── middlewares/
│   │   ├── localization.py # i18n / multi-language support
│   │   └── __init__.py
│   ├── services/
│   │   ├── gemini_service.py   # Gemini AI + model ranking + transcription
│   │   ├── tts_service.py      # Text-to-Speech
│   │   └── __init__.py
│   ├── states/
│   │   ├── app_states.py   # FSM states
│   │   └── __init__.py
│   ├── utils/
│   │   ├── message_utils.py
│   │   └── __init__.py
│   └── __init__.py
├── database/
│   ├── db_utils.py
│   └── __init__.py
└── locales/                # i18n translation files
    ├── ar.json  ├── de.json  ├── en.json  ├── es.json
    ├── fr.json  ├── hi.json  ├── hy.json  ├── it.json
    ├── ja.json  ├── ko.json  ├── pt.json  ├── ru.json
    └── zh.json
```

---

## Installation

### Prerequisites

- Python 3.8 or higher
- Telegram Bot Token (from [@BotFather](https://t.me/BotFather))
- Google Gemini API Key (from [Google AI Studio](https://aistudio.google.com/))

### Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd Arvion_Lingua_AI/Arvion_Lingua_AI
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Create a `.env` file**
   ```env
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token_here
   GEMINI_API_KEY=your_gemini_api_key_here
   DB_NAME=lingua_ai_bot.db
   GEMINI_MODEL=gemini-2.5-flash
   ```

5. **Run the bot**
   ```bash
   python main.py
   ```

> ⚠️ **Important:** Make sure only **one instance** of the bot is running. If you need to restart:
> ```bash
> pkill -9 -f "python3 main.py"
> python main.py
> ```

---

## Environment Variables

| Variable | Description | Default |
|----------|------------|---------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | Required |
| `GEMINI_API_KEY` | Google Gemini API key | Required |
| `DB_NAME` | SQLite database filename | `lingua_ai_bot.db` |
| `GEMINI_MODEL` | Default/fallback Gemini model | `gemini-2.5-flash` |

---

## Database Schema

### Users Table
- `user_id` — Telegram user ID (Primary Key)
- `interface_lang` — Bot interface language
- `native_lang` — User's native language
- `learning_lang` — Language being learned
- `learning_level` — Current learning level
- `programming_lang` — Preferred programming language
- `programming_level` — Programming skill level
- `learning_mode` — Learning mode (human / programming)
- `translations_count`, `words_learned_count`, `quizzes_passed_count`, `facts_requested_count`, `streak_count`
- `last_activity_date` — Last interaction date

### Chat History Table
- `id` — Record ID (Auto-increment)
- `user_id` — Foreign Key to users
- `role` — Message role (`user` / `model`)
- `content` — Message content
- `timestamp` — Message timestamp

---

## Usage

### Commands

| Command | Description |
|---------|------------|
| `/start` | Initialize bot and create user profile |
| `/settings` | Configure language preferences |
| `/stats` | View your learning statistics |
| `/fact` | Get a fun cultural or tech fact |
| `/models` | View ranked Gemini models list & active status |
| `/reset` | Clear current chat history |

### Main Menu Buttons

| Button | Feature |
|--------|---------|
| 🌐 Translate | Text & image translation |
| 🎓 Learn | Language / programming exercises |
| 🤖 Chat with AI | Text & **voice** conversation |
| ⚙️ Settings | User preferences |

### 🎤 How to Use Voice Chat

1. Open the bot → Tap **🤖 Chat with AI**
2. Send a **voice message** 🎙️
3. The bot will:
   - Show `🎤...` while processing
   - Display: `You: [your transcribed text]` + AI reply
   - Send back a **voice message** with the response
4. Works in regular chat and all role-play scenarios!

---

## Key Components

### GeminiService

- **`_initialize_models()`** — Fetches all API-available models and ranks them by capability
- **`_safe_generate()`** — Tries models in order; falls back automatically on failure
- **`chat_with_ai()`** — Context-aware chat with full history and fallback
- **`transcribe_audio()`** — Transcribes voice messages to text using multimodal Gemini
- **`translate_text()`** — Language translation
- **`get_learning_item()`** — Generates vocabulary, concepts, quizzes

---

## Error Handling

- **API failures** gracefully fall back to the next best model
- **Quota exhausted (429)** — bot tries alternative models automatically
- **Transcription failures** — user receives a clear localized error message
- **Database errors** — logged, user sees a friendly message
- **Conflict errors** — ensure only one bot instance runs at a time

---

## Development

### Adding a New Language
1. Add the language code to `SUPPORTED_LANGUAGES` in `config.py`
2. Create a `locales/<code>.json` file following the structure of `en.json`
3. Add the new locale keys: `could_not_understand_audio`, `voice_error`, etc.

### Adding a New Feature
1. Create a handler in `bot/handlers/`
2. Add FSM states in `bot/states/app_states.py` if needed
3. Create keyboards in `bot/keyboards/` if needed
4. Register the router in `main.py`

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/AmazingFeature`
3. Commit changes: `git commit -m 'Add AmazingFeature'`
4. Push: `git push origin feature/AmazingFeature`
5. Open a Pull Request

---

## License

This project is provided as-is for educational and personal use.

## Acknowledgments

- [aiogram](https://github.com/aiogram/aiogram) — Modern Telegram Bot API framework
- [Google Generative AI](https://ai.google.dev/) — Gemini AI models
- [gTTS](https://github.com/pndurette/gTTS) — Text-to-Speech

---

**Version**: 2.0.0
**Last Updated**: May 2026
**Status**: Active Development
**Bot**: [@Arvion_Lingua_AI_Bot](https://t.me/Arvion_Lingua_AI_Bot)
