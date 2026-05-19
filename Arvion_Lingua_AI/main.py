import asyncio
import logging
from pathlib import Path

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_TOKEN
from database.db_utils import init_db
from bot.middlewares.localization import Localization, get_all_translations
from bot.handlers import (
    common_handlers,
    settings_handlers,
    translate_handlers,
    learning_handlers,
    chat_handlers,
)
from bot.handlers.onboarding_handlers import onboarding_router
from bot.handlers.vocab_handlers import vocab_router
from bot.handlers.flashcard_handlers import flashcard_router
from bot.handlers.extra_handlers import extra_router
from bot.handlers.pronunciation_handlers import pronunciation_router
from bot.handlers.games_handlers import games_router
from bot.handlers.culture_grammar_handlers import culture_grammar_router

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s - %(levelname)s - %(name)s - "
            "[%(filename)s:%(lineno)d] - %(message)s"
        ),
    )

    if not TELEGRAM_TOKEN:
        logging.critical("TELEGRAM_BOT_TOKEN not found in .env file. Please check your .env file.")
        return

    await init_db()

    bot = Bot(
        token=TELEGRAM_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)

    locales_dir = Path(__file__).parent / "locales"
    loc_middleware = Localization(locales_dir=locales_dir)
    dp.update.middleware(loc_middleware)
    bot.loc_middleware = loc_middleware

    # Onboarding router must be first to intercept /start for new users
    dp.include_router(onboarding_router)
    dp.include_router(common_handlers.common_router)
    dp.include_router(settings_handlers.settings_router)
    dp.include_router(translate_handlers.translate_router)
    dp.include_router(learning_handlers.learning_router)
    dp.include_router(chat_handlers.chat_router)
    dp.include_router(vocab_router)
    dp.include_router(flashcard_router)
    dp.include_router(extra_router)
    dp.include_router(pronunciation_router)
    dp.include_router(games_router)
    dp.include_router(culture_grammar_router)

    # ------------------ Reply Keyboard Handlers ------------------
    all_translate_texts = get_all_translations("translate_button", loc_middleware.locales)
    @dp.message(F.text.in_(all_translate_texts))
    async def handle_translate_text(message, user_db, state):
        await translate_handlers.cb_enter_translator(message, user_db, state)

    all_learn_texts = get_all_translations("learn_button", loc_middleware.locales)
    @dp.message(F.text.in_(all_learn_texts))
    async def handle_learn_text(message, user_db, state):
        await learning_handlers.cb_main_menu_learn(message, user_db, state)

    all_chat_texts = get_all_translations("chat_button", loc_middleware.locales)
    @dp.message(F.text.in_(all_chat_texts))
    async def handle_chat_text(message, state):
        await chat_handlers.cb_chat_entry(message, state)

    all_settings_texts = get_all_translations("settings_button", loc_middleware.locales)
    @dp.message(F.text.in_(all_settings_texts))
    async def handle_settings_text(message, user_db, state):
        await settings_handlers.cb_main_menu_settings(message, user_db, state)

    all_games_texts = get_all_translations("games_button", loc_middleware.locales)
    @dp.message(F.text.in_(all_games_texts))
    async def handle_games_text(message, user_db, state):
        i18n = getattr(message.bot, "i18n", {})
        from bot.handlers.games_handlers import show_games_menu
        await show_games_menu(message, i18n, state)

    all_culture_texts = get_all_translations("culture_button", loc_middleware.locales)
    @dp.message(F.text.in_(all_culture_texts))
    async def handle_culture_text(message, user_db, state):
        from bot.handlers.culture_grammar_handlers import cmd_culture
        await cmd_culture(message, user_db, state)
    # -----------------------------------------------------------

    try:
        # Սա լավ պրակտիկա է՝ համոզվելու համար, որ հին webhook-ները չեն խանգարում
        await bot.delete_webhook(drop_pending_updates=True)

        # Set bot command menu visible in Telegram
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="start",       description="🔄 Restart / Main menu"),
            BotCommand(command="menu",        description="🏠 Go to main menu"),
            BotCommand(command="stats",       description="📊 Your progress & badges"),
            BotCommand(command="vocab",       description="📖 Your vocabulary book"),
            BotCommand(command="review",      description="🃏 Flashcard review (spaced repetition)"),
            BotCommand(command="wotd",        description="📖 Word of the Day"),
            BotCommand(command="challenge",   description="🎯 Daily challenge"),
            BotCommand(command="leaderboard", description="🏆 Global leaderboard"),
            BotCommand(command="grammar",     description="📚 Grammar Guide"),
            BotCommand(command="culture",     description="🌍 Culture Corner"),
            BotCommand(command="summary",     description="📊 Chat session summary"),
            BotCommand(command="fact",        description="💡 Fun fact about your language"),
            BotCommand(command="models",      description="🤖 Active AI models"),
            BotCommand(command="help",        description="❓ All commands"),
        ])
        logging.info("Bot commands set successfully.")

        # Սկսում ենք Polling ռեժիմը
        await dp.start_polling(bot)
    except Exception as e:
        logging.critical(f"An error occurred during polling: {e}")
    finally:
        if bot.session:
            await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped manually.")