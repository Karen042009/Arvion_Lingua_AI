import aiosqlite
import logging
from config import DB_NAME
from datetime import date, timedelta

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                interface_lang TEXT DEFAULT 'en',
                native_lang TEXT DEFAULT 'en',
                learning_lang TEXT DEFAULT 'es',
                learning_level TEXT DEFAULT 'beginner',
                programming_lang TEXT DEFAULT 'python',
                programming_level TEXT DEFAULT 'beginner',
                learning_mode TEXT DEFAULT 'human',
                translations_count INTEGER DEFAULT 0,
                words_learned_count INTEGER DEFAULT 0,
                quizzes_passed_count INTEGER DEFAULT 0,
                facts_requested_count INTEGER DEFAULT 0,
                streak_count INTEGER DEFAULT 0,
                last_activity_date TEXT DEFAULT '1970-01-01',
                onboarding_complete INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS chat_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS saved_words (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                word TEXT NOT NULL,
                translation TEXT NOT NULL,
                language TEXT NOT NULL,
                saved_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS achievements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                badge_key TEXT NOT NULL,
                unlocked_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, badge_key),
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS daily_challenge (
                user_id INTEGER PRIMARY KEY,
                challenge_date TEXT NOT NULL,
                challenge_type TEXT NOT NULL,
                target INTEGER NOT NULL DEFAULT 5,
                progress INTEGER NOT NULL DEFAULT 0,
                completed INTEGER NOT NULL DEFAULT 0,
                FOREIGN KEY (user_id) REFERENCES users (user_id)
            )
        ''')
        # Migrate existing tables: add missing columns if they don't exist
        migrations = [
            "ALTER TABLE users ADD COLUMN onboarding_complete INTEGER DEFAULT 0",
            "ALTER TABLE users ADD COLUMN username TEXT DEFAULT ''",
            "ALTER TABLE saved_words ADD COLUMN next_review_date TEXT DEFAULT ''",
            "ALTER TABLE saved_words ADD COLUMN interval_days INTEGER DEFAULT 1",
            "ALTER TABLE saved_words ADD COLUMN ease_factor REAL DEFAULT 2.5",
            "ALTER TABLE saved_words ADD COLUMN review_count INTEGER DEFAULT 0",
        ]
        for migration in migrations:
            try:
                await db.execute(migration)
            except Exception:
                pass  # Column already exists
        await db.commit()
    logging.info("Database initialized.")

async def get_or_create_user(user_id: int) -> dict | None:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        )
        user = await cursor.fetchone()
        if not user:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
            )
            await db.commit()
            cursor = await db.execute(
                "SELECT * FROM users WHERE user_id = ?", (user_id,)
            )
            user = await cursor.fetchone()
    return dict(user) if user else None

async def update_user_setting(
    user_id: int, setting_name: str, setting_value: str
):
    valid_columns = [
        'interface_lang', 'native_lang', 'learning_lang', 'learning_level',
        'programming_lang', 'programming_level', 'learning_mode'
    ]
    if setting_name not in valid_columns:
        logging.error(f"Attempt to update invalid column: {setting_name}")
        return

    query = f"UPDATE users SET {setting_name} = ? WHERE user_id = ?"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(query, (setting_value, user_id))
        await db.commit()
    logging.info(f"User {user_id} updated {setting_name} to {setting_value}")

async def update_daily_streak(user_id: int):
    today = date.today()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT streak_count, last_activity_date FROM users WHERE user_id = ?",
            (user_id,)
        )
        user_data = await cursor.fetchone()
        if not user_data:
            return

        last_activity_date_str = user_data['last_activity_date']
        if last_activity_date_str == today.isoformat():
            return

        last_activity = date.fromisoformat(last_activity_date_str)
        yesterday = today - timedelta(days=1)

        if last_activity == yesterday:
            new_streak = user_data['streak_count'] + 1
        else:
            new_streak = 1

        await db.execute(
            "UPDATE users SET streak_count = ?, last_activity_date = ? WHERE user_id = ?",
            (new_streak, today.isoformat(), user_id)
        )
        await db.commit()
        logging.info(f"User {user_id} streak updated to {new_streak}")

async def increment_user_stat(user_id: int, stat_name: str):
    await update_daily_streak(user_id)
    valid_stats = [
        'translations_count', 'words_learned_count',
        'quizzes_passed_count', 'facts_requested_count'
    ]
    if stat_name not in valid_stats:
        logging.warning(f"Attempt to increment invalid stat: {stat_name}")
        return

    query = f"UPDATE users SET {stat_name} = {stat_name} + 1 WHERE user_id = ?"
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(query, (user_id,))
        await db.commit()

async def get_chat_history(user_id: int, limit: int = 20) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        query = (
            "SELECT role, content FROM chat_history "
            "WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?"
        )
        cursor = await db.execute(query, (user_id, limit))
        rows = await cursor.fetchall()
        return [
            {"role": row["role"], "parts": [{"text": row["content"]}]}
            for row in reversed(rows)
        ]

async def add_to_chat_history(user_id: int, role: str, content: str):
    async with aiosqlite.connect(DB_NAME) as db:
        query = "INSERT INTO chat_history (user_id, role, content) VALUES (?, ?, ?)"
        await db.execute(query, (user_id, role, content))
        await db.commit()

async def clear_chat_history(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("DELETE FROM chat_history WHERE user_id = ?", (user_id,))
        await db.commit()
    logging.info(f"Chat history cleared for user {user_id}")

async def save_word(user_id: int, word: str, translation: str, language: str):
    async with aiosqlite.connect(DB_NAME) as db:
        # Avoid duplicates
        cursor = await db.execute(
            "SELECT id FROM saved_words WHERE user_id = ? AND word = ? AND language = ?",
            (user_id, word, language)
        )
        existing = await cursor.fetchone()
        if not existing:
            await db.execute(
                "INSERT INTO saved_words (user_id, word, translation, language) VALUES (?, ?, ?, ?)",
                (user_id, word, translation, language)
            )
            await db.commit()
            return True
        return False

async def get_saved_words(user_id: int, limit: int = 50) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT word, translation, language, saved_at FROM saved_words "
            "WHERE user_id = ? ORDER BY saved_at DESC LIMIT ?",
            (user_id, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

async def delete_saved_word(user_id: int, word: str, language: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "DELETE FROM saved_words WHERE user_id = ? AND word = ? AND language = ?",
            (user_id, word, language)
        )
        await db.commit()

async def get_saved_words_count(user_id: int) -> int:
    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "SELECT COUNT(*) FROM saved_words WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

async def set_onboarding_complete(user_id: int):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET onboarding_complete = 1 WHERE user_id = ?", (user_id,)
        )
        await db.commit()


async def update_username(user_id: int, username: str):
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "UPDATE users SET username = ? WHERE user_id = ?", (username or "", user_id)
        )
        await db.commit()


# ─── Leaderboard ────────────────────────────────────────────────────────────

async def get_leaderboard(limit: int = 10) -> list:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT user_id, username, quizzes_passed_count, streak_count "
            "FROM users ORDER BY quizzes_passed_count DESC LIMIT ?",
            (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


# ─── Achievements ────────────────────────────────────────────────────────────

BADGE_THRESHOLDS = {
    "first_translation":  ("translations_count", 1,  "🌐 First Translation"),
    "translator_10":      ("translations_count", 10, "🌐 Translator"),
    "translator_50":      ("translations_count", 50, "🌐 Pro Translator"),
    "first_word":         ("words_learned_count", 1,  "📝 First Word"),
    "word_master_20":     ("words_learned_count", 20, "📚 Word Master"),
    "word_master_100":    ("words_learned_count", 100,"📚 Vocabulary Expert"),
    "first_quiz":         ("quizzes_passed_count", 1,  "🧩 First Quiz"),
    "quiz_champ_10":      ("quizzes_passed_count", 10, "🧩 Quiz Champion"),
    "quiz_champ_50":      ("quizzes_passed_count", 50, "🧩 Quiz Master"),
    "streak_3":           ("streak_count", 3,  "🔥 3-Day Streak"),
    "streak_7":           ("streak_count", 7,  "🔥 Week Streak"),
    "streak_30":          ("streak_count", 30, "⚡ Month Streak"),
}


async def get_unlocked_badges(user_id: int) -> set:
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT badge_key FROM achievements WHERE user_id = ?", (user_id,)
        )
        rows = await cursor.fetchall()
        return {row["badge_key"] for row in rows}


async def check_and_unlock_badges(user_id: int, user_db: dict) -> list[str]:
    """Returns list of newly unlocked badge display names."""
    already_unlocked = await get_unlocked_badges(user_id)
    newly_unlocked = []

    async with aiosqlite.connect(DB_NAME) as db:
        for badge_key, (stat_col, threshold, display_name) in BADGE_THRESHOLDS.items():
            if badge_key in already_unlocked:
                continue
            if user_db.get(stat_col, 0) >= threshold:
                try:
                    await db.execute(
                        "INSERT OR IGNORE INTO achievements (user_id, badge_key) VALUES (?, ?)",
                        (user_id, badge_key)
                    )
                    newly_unlocked.append(display_name)
                except Exception:
                    pass
        await db.commit()

    return newly_unlocked


# ─── Daily Challenge ─────────────────────────────────────────────────────────

async def get_or_create_daily_challenge(user_id: int) -> dict:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM daily_challenge WHERE user_id = ?", (user_id,)
        )
        row = await cursor.fetchone()

        if row and row["challenge_date"] == today:
            return dict(row)

        # New day — create fresh challenge
        import random
        challenge_types = ["quiz", "word", "translate"]
        challenge_type = random.choice(challenge_types)
        target = 5

        await db.execute(
            """INSERT OR REPLACE INTO daily_challenge
               (user_id, challenge_date, challenge_type, target, progress, completed)
               VALUES (?, ?, ?, ?, 0, 0)""",
            (user_id, today, challenge_type, target)
        )
        await db.commit()
        return {
            "user_id": user_id,
            "challenge_date": today,
            "challenge_type": challenge_type,
            "target": target,
            "progress": 0,
            "completed": 0,
        }


async def update_daily_challenge_progress(user_id: int, activity_type: str):
    """Increment progress if activity matches today's challenge type."""
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT * FROM daily_challenge WHERE user_id = ? AND challenge_date = ?",
            (user_id, today)
        )
        row = await cursor.fetchone()
        if not row or row["completed"]:
            return False

        if row["challenge_type"] != activity_type:
            return False

        new_progress = row["progress"] + 1
        completed = 1 if new_progress >= row["target"] else 0

        await db.execute(
            "UPDATE daily_challenge SET progress = ?, completed = ? WHERE user_id = ?",
            (new_progress, completed, user_id)
        )
        await db.commit()
        return completed == 1  # Returns True if just completed


# ─── Flashcard / Spaced Repetition ──────────────────────────────────────────

async def get_words_due_for_review(user_id: int, limit: int = 10) -> list:
    today = date.today().isoformat()
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            """SELECT id, word, translation, language, interval_days, ease_factor, review_count
               FROM saved_words
               WHERE user_id = ? AND (next_review_date = '' OR next_review_date <= ?)
               ORDER BY next_review_date ASC, saved_at ASC
               LIMIT ?""",
            (user_id, today, limit)
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def update_word_review(user_id: int, word_id: int, quality: int):
    """
    SM-2 spaced repetition algorithm.
    quality: 0-5 (0=blackout, 3=correct with difficulty, 5=perfect)
    """
    async with aiosqlite.connect(DB_NAME) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT interval_days, ease_factor, review_count FROM saved_words WHERE id = ? AND user_id = ?",
            (word_id, user_id)
        )
        row = await cursor.fetchone()
        if not row:
            return

        interval = row["interval_days"]
        ease = row["ease_factor"]
        count = row["review_count"]

        if quality < 3:
            interval = 1
        else:
            if count == 0:
                interval = 1
            elif count == 1:
                interval = 6
            else:
                interval = round(interval * ease)

        ease = max(1.3, ease + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        next_review = (date.today() + timedelta(days=interval)).isoformat()

        await db.execute(
            """UPDATE saved_words
               SET interval_days = ?, ease_factor = ?, review_count = review_count + 1,
                   next_review_date = ?
               WHERE id = ? AND user_id = ?""",
            (interval, ease, next_review, word_id, user_id)
        )
        await db.commit()