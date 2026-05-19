"""
Extra commands:
  /leaderboard  — top 10 users by quizzes
  /challenge    — today's daily challenge
  /wotd         — word of the day
  /summary      — AI summary of current chat session
"""
import html
import logging
from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message, InlineQueryResultArticle, InputTextMessageContent
from aiogram import F

from bot.middlewares.localization import _
from bot.services.gemini_service import GeminiService
from bot.utils.message_utils import send_safe_html
from database.db_utils import (
    get_leaderboard, get_or_create_daily_challenge,
    get_chat_history, check_and_unlock_badges, update_username
)
from config import SUPPORTED_LANGUAGES, SUPPORTED_PROGRAMMING_LANGUAGES, LEARNING_LEVELS

extra_router = Router()
gemini_service = GeminiService()


# ─── /leaderboard ────────────────────────────────────────────────────────────

@extra_router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, user_db: dict):
    i18n = getattr(message.bot, "i18n", {})

    # Save/update username
    tg_user = message.from_user
    display_name = tg_user.username or tg_user.first_name or f"User{tg_user.id}"
    await update_username(tg_user.id, display_name)

    rows = await get_leaderboard(limit=10)
    if not rows:
        await message.answer(_("leaderboard_empty", i18n))
        return

    medals = ["🥇", "🥈", "🥉"]
    text = f"<b>🏆 {_('leaderboard_title', i18n)}</b>\n\n"

    for idx, row in enumerate(rows, 1):
        medal = medals[idx - 1] if idx <= 3 else f"{idx}."
        name = html.escape(row.get("username") or f"User{row['user_id']}")
        quizzes = row.get("quizzes_passed_count", 0)
        streak = row.get("streak_count", 0)
        is_me = "  ← <i>you</i>" if row["user_id"] == message.from_user.id else ""
        text += f"{medal} <b>{name}</b> — {quizzes} quizzes 🧩  🔥{streak}{is_me}\n"

    await send_safe_html(message, text)


# ─── /challenge ───────────────────────────────────────────────────────────────

@extra_router.message(Command("challenge"))
async def cmd_challenge(message: Message, user_db: dict):
    i18n = getattr(message.bot, "i18n", {})
    challenge = await get_or_create_daily_challenge(message.from_user.id)

    c_type = challenge["challenge_type"]
    progress = challenge["progress"]
    target = challenge["target"]
    completed = challenge["completed"]

    filled = min(int((progress / target) * 10), 10)
    bar = "█" * filled + "░" * (10 - filled)

    type_emoji = {"quiz": "🧩", "word": "📝", "translate": "🌐"}.get(c_type, "🎯")
    type_label = _("challenge_type_" + c_type, i18n)

    if completed:
        status = "✅ " + _("challenge_completed", i18n)
    else:
        status = f"{bar} {progress}/{target}"

    text = (
        f"<b>🎯 {_('daily_challenge_title', i18n)}</b>\n\n"
        f"{type_emoji} <b>{type_label}</b>\n"
        f"{_('challenge_goal', i18n, target=target)}\n\n"
        f"{status}"
    )

    if not completed:
        text += f"\n\n💡 {_('challenge_tip', i18n)}"

    await message.answer(text)


# ─── /wotd ────────────────────────────────────────────────────────────────────

@extra_router.message(Command("wotd"))
async def cmd_wotd(message: Message, user_db: dict):
    i18n = getattr(message.bot, "i18n", {})
    processing_msg = await message.answer("📖...")

    mode = user_db.get("learning_mode", "human")
    if mode != "human":
        await processing_msg.delete()
        await message.answer(_("wotd_human_only", i18n))
        return

    learning_lang = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["gemini_name"]
    native_lang = SUPPORTED_LANGUAGES[user_db["native_lang"]]["gemini_name"]
    level = LEARNING_LEVELS[user_db["learning_level"]]

    result = await gemini_service.get_word_of_the_day(learning_lang, native_lang, level)
    await processing_msg.delete()

    if not result:
        await message.answer(_("generation_error", i18n))
        return

    word = html.escape(result.get("word", ""))
    translation = html.escape(result.get("translation", ""))
    example = html.escape(result.get("example", ""))
    example_tr = html.escape(result.get("example_translation", ""))
    pos = html.escape(result.get("part_of_speech", ""))

    text = (
        f"📖 <b>{_('wotd_title', i18n)}</b>\n\n"
        f"<b>{word}</b>"
        + (f" <i>({pos})</i>" if pos else "") +
        f"\n🔤 {translation}\n\n"
        f"📝 <i>{example}</i>\n"
        f"   {example_tr}"
    )

    await send_safe_html(message, text)


# ─── /summary ─────────────────────────────────────────────────────────────────

@extra_router.message(Command("summary"))
async def cmd_summary(message: Message, user_db: dict):
    i18n = getattr(message.bot, "i18n", {})
    processing_msg = await message.answer("🤖 " + _("generating_summary", i18n))

    history = await get_chat_history(message.from_user.id, limit=40)
    if not history:
        await processing_msg.delete()
        await message.answer(_("summary_no_history", i18n))
        return

    interface_lang = SUPPORTED_LANGUAGES[user_db["interface_lang"]]["gemini_name"]
    summary = await gemini_service.summarize_conversation(history, interface_lang)
    await processing_msg.delete()

    if not summary:
        await message.answer(_("generation_error", i18n))
        return

    text = f"<b>📊 {_('summary_title', i18n)}</b>\n\n{html.escape(summary)}"
    await send_safe_html(message, text)


# ─── Inline Mode ──────────────────────────────────────────────────────────────

@extra_router.inline_query()
async def inline_translate(inline_query, bot):
    """@bot_username <text> — translate from any chat."""
    query_text = inline_query.query.strip()
    if not query_text:
        await inline_query.answer([], cache_time=1)
        return

    try:
        result = await gemini_service.translate_text(query_text, "English", "auto")
        if result and result.get("translated_text"):
            translated = result["translated_text"]
            detected = result.get("detected_language_name", "?")
            answer_text = f"🌐 {detected} → English\n\n{translated}"
        else:
            answer_text = "❌ Translation failed."

        results = [
            InlineQueryResultArticle(
                id="1",
                title=f"Translate: {query_text[:30]}",
                description=answer_text[:100],
                input_message_content=InputTextMessageContent(
                    message_text=answer_text
                ),
            )
        ]
        await inline_query.answer(results, cache_time=30)
    except Exception as e:
        logging.error(f"Inline translate error: {e}")
        await inline_query.answer([], cache_time=1)
