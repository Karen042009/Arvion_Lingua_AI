# Arvion Lingua AI 🤖🌍

A powerful Telegram bot for language learning, AI-powered voice chat, and translation — built on Google Gemini AI.

---

## Features

### 🌐 Translation
- Translate text between **13 supported languages**
- Auto-detect source language
- Swap source/target languages instantly
- **Image OCR + translation** — send a photo, get the text translated
- TTS pronunciation for both source and translated text

### 🎓 Learn (Language Learning)
- Adaptive levels: **A1/A2**, **B1/B2**, **C1/C2**
- **New Word** — AI-generated vocabulary with translation
- **Quiz** — multiple choice questions with instant feedback
- **Fill in the Blank** — sentence completion exercises
- **Story Mode** — read a short story, then answer comprehension questions
- **Idiom of the Day** — learn idiomatic expressions with examples
- **Grammar Check** — submit a sentence, get AI-powered correction and explanation
- Daily streak tracking and progress statistics

### 🎮 Games (Separate from Learning)
- **Word Scramble 🔀** — unscramble a word given a hint and translation
- **Hangman 🎯** — guess the word letter by letter
- **Speed Round ⚡** — translate as many words as possible in 30 seconds
- All games are AI-generated and adapt to your language and level

### 🤖 Chat with AI
- **Regular Chat** — open-ended conversation with Gemini
- **Role-Play Scenarios**:
  - ☕ At the Cafe
  - 🏨 At the Hotel
  - 💼 Job Interview
  - 🏥 At the Doctor
  - ✈️ At the Airport
  - 🛍️ Shopping
- **Voice message support** — send a voice message, get a text + voice reply
- Persistent chat history per session
- `/summary` — AI summary of your current chat session

### 🌍 Culture & Grammar
- **Grammar Guide** (`/grammar`) — topic-based grammar lessons with rules, examples, and practice sentences; adapts to your current level
- **Culture Corner** (`/culture`) — explore food, traditions, history, music, etiquette, landmarks, and more for your target language

### 💻 Programming Learning
- 10 languages: Python, JavaScript, Java, C#, C++, PHP, Swift, Kotlin, SQL, Go
- Three levels: Beginner, Intermediate, Advanced
- Concept explanations with code examples
- Interactive coding quizzes

### 🃏 Flashcard Review (Spaced Repetition)
- Save words to your personal vocabulary book during learning
- `/review` — flashcard-style review with spaced repetition scheduling
- Rate each card: Hard / OK / Easy — next review interval adjusts automatically

### 🔊 Text-to-Speech
- Converts AI responses to audio using gTTS
- Multi-language audio support
- Voiced in your selected learning language

### 📊 Statistics & Badges
- Translations count, words learned, quizzes passed, facts requested
- Daily activity streak with milestone badges
- `/stats` — full progress overview with progress bars
- `/leaderboard` — global top 10 by quizzes and streak

### 🎯 Daily Challenge
- `/challenge` — a fresh daily goal (translate X texts, learn X words, pass X quizzes)
- Progress bar updates in real time

### 💡 Fun Facts
- `/fact` — AI-generated fun fact about your learning language or programming language

### 🏆 Smart Model Auto-Ranking & Fallback
- The bot dynamically fetches all Gemini models available on your API key and ranks them by capability
- If the top model hits a quota limit or error, it **automatically falls back** to the next best model
- `/models` — see the live ranked priority queue and fallback status

### ⚙️ Settings
- Interface language (13 languages)
- Native language
- Learning language & level
- Programming language & level
- Learning mode (Human Languages / Programming)

---

## Bot Commands

| Command | Description |
|---------|-------------|
| `/start` | Start the bot / restart onboarding |
| `/menu` | Go to main menu |
| `/stats` | Your progress and badges |
| `/vocab` | Your saved vocabulary book |
| `/review` | Flashcard review (spaced repetition) |
| `/wotd` | Word of the Day |
| `/challenge` | Today's daily challenge |
| `/leaderboard` | Global leaderboard |
| `/grammar` | Grammar Guide |
| `/culture` | Culture Corner |
| `/summary` | AI summary of current chat session |
| `/fact` | Fun fact about your language |
| `/models` | Active AI models and fallback status |
| `/help` | All commands |

---

## Main Menu

| Button | Section |
|--------|---------|
| 🌐 Translate | Text & image translation with TTS |
| 🎓 Learn | Vocabulary, quizzes, stories, grammar check |
| 🤖 Chat with AI | Text & voice conversation, role-play |
| ⚙️ Settings | User preferences |
| 🎮 Games | Word Scramble, Hangman, Speed Round |
| 🌍 Culture & Grammar | Grammar lessons and culture topics |

---

## Supported Languages

| Code | Language    | Code | Language    |
|------|-------------|------|-------------|
| en   | English     | ja   | Japanese    |
| hy   | Armenian    | ko   | Korean      |
| ru   | Russian     | hi   | Hindi       |
| es   | Spanish     | ar   | Arabic      |
| fr   | French      | de   | German      |
| it   | Italian     | pt   | Portuguese  |
| zh   | Chinese     |      |             |

---

## Tech Stack

| Component | Technology |
|-----------|------------|
| Language | Python 3.8+ |
| Bot Framework | aiogram 3.5.0 |
| AI Engine | Google Generative AI (Gemini) |
| Database | SQLite (async via aiosqlite) |
| Text-to-Speech | gTTS 2.5.1 |
| Image Processing | Pillow 10.3.0 |

---

## Project Structure

```
Arvion_Lingua_AI/
├── main.py                        # Bot entry point & router setup
├── config.py                      # Configuration and constants
├── requirements.txt               # Python dependencies
├── .env                           # Environment variables (not tracked)
├── bot/
│   ├── handlers/
│   │   ├── common_handlers.py     # /start, /menu, /stats, /fact, /models, /help
│   │   ├── onboarding_handlers.py # First-run setup flow
│   │   ├── translate_handlers.py  # Translation + image OCR
│   │   ├── learning_handlers.py   # Word, quiz, fill-blank, story, idiom, grammar check
│   │   ├── games_handlers.py      # Word Scramble, Hangman, Speed Round
│   │   ├── culture_grammar_handlers.py  # Grammar Guide + Culture Corner
│   │   ├── chat_handlers.py       # Chat + voice + role-play
│   │   ├── settings_handlers.py   # User settings
│   │   ├── vocab_handlers.py      # Vocabulary book
│   │   ├── flashcard_handlers.py  # Spaced repetition review
│   │   ├── pronunciation_handlers.py
│   │   └── extra_handlers.py      # /leaderboard, /challenge, /wotd, /summary, inline
│   ├── keyboards/
│   │   ├── inline.py
│   │   └── reply.py
│   ├── middlewares/
│   │   └── localization.py        # i18n / multi-language support
│   ├── services/
│   │   ├── gemini_service.py      # Gemini AI, model ranking, transcription
│   │   └── tts_service.py         # Text-to-Speech
│   ├── states/
│   │   └── app_states.py          # FSM states
│   └── utils/
│       └── message_utils.py
├── database/
│   └── db_utils.py
└── locales/                       # i18n translation files (13 languages)
    ├── en.json  ├── hy.json  ├── ru.json  ├── es.json
    ├── fr.json  ├── de.json  ├── it.json  ├── pt.json
    ├── zh.json  ├── ja.json  ├── ko.json  ├── hi.json
    └── ar.json
```

---

## Installation

### Prerequisites

- Python 3.8+
- Telegram Bot Token — from [@BotFather](https://t.me/BotFather)
- Google Gemini API Key — from [Google AI Studio](https://aistudio.google.com/)

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
   GEMINI_MODEL=gemini-flash-latest
   ```

5. **Run the bot**
   ```bash
   python main.py
   ```

> ⚠️ Make sure only **one instance** of the bot is running at a time.
> ```bash
> pkill -9 -f "python3 main.py"
> python main.py
> ```

---

## Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `TELEGRAM_BOT_TOKEN` | Your Telegram bot token | ✅ |
| `GEMINI_API_KEY` | Google Gemini API key | ✅ |
| `DB_NAME` | SQLite database filename | optional |
| `GEMINI_MODEL` | Default/fallback Gemini model | optional |

---

## Database Schema

**Users table** — stores per-user settings and stats:
`user_id`, `interface_lang`, `native_lang`, `learning_lang`, `learning_level`, `programming_lang`, `programming_level`, `learning_mode`, `translations_count`, `words_learned_count`, `quizzes_passed_count`, `facts_requested_count`, `streak_count`, `last_activity_date`, `onboarding_complete`

**Chat history table** — stores conversation context:
`id`, `user_id`, `role` (user/model), `content`, `timestamp`

**Vocabulary table** — saved words per user:
`id`, `user_id`, `word`, `translation`, `language`, `next_review`, `review_count`, `ease_factor`

---

## Development

### Adding a New Language
1. Add the language code to `SUPPORTED_LANGUAGES` in `config.py`
2. Create `locales/<code>.json` following the structure of `en.json`

### Adding a New Feature
1. Create a handler in `bot/handlers/`
2. Add FSM states in `bot/states/app_states.py` if needed
3. Register the router in `main.py`

---

## Acknowledgments

- [aiogram](https://github.com/aiogram/aiogram) — Telegram Bot API framework
- [Google Generative AI](https://ai.google.dev/) — Gemini AI models
- [gTTS](https://github.com/pndurette/gTTS) — Text-to-Speech

---

**Version**: 2.1.0
**Last Updated**: May 2026
**Status**: Active Development
**Bot**: [@Arvion_Lingua_AI_Bot](https://t.me/Arvion_Lingua_AI_Bot)
