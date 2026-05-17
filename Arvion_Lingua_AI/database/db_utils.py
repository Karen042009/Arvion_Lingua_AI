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
                last_activity_date TEXT DEFAULT '1970-01-01'
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