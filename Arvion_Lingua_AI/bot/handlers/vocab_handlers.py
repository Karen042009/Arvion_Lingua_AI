"""
Vocabulary book: /vocab command to view saved words.
Words are saved during learning sessions via the 💾 Save button.
"""
import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.middlewares.localization import _
from bot.utils.message_utils import send_safe_html
from database.db_utils import get_saved_words, get_saved_words_count

vocab_router = Router()

WORDS_PER_PAGE = 10


@vocab_router.message(Command("vocab"))
async def cmd_vocab(message: Message, user_db: dict):
    i18n = getattr(message.bot, "i18n", {})
    user_id = message.from_user.id

    words = await get_saved_words(user_id, limit=50)
    count = await get_saved_words_count(user_id)

    if not words:
        await message.answer(_("vocab_empty", i18n))
        return

    # Group by language
    by_lang: dict[str, list] = {}
    for w in words:
        lang = w["language"]
        by_lang.setdefault(lang, []).append(w)

    text = _("vocab_header", i18n, count=count) + "\n\n"

    for lang, items in by_lang.items():
        text += f"<b>🌐 {html.escape(lang)}</b>\n"
        for w in items[:WORDS_PER_PAGE]:
            word = html.escape(w["word"])
            translation = html.escape(w["translation"])
            text += f"  • <b>{word}</b> — {translation}\n"
        if len(items) > WORDS_PER_PAGE:
            text += f"  <i>...and {len(items) - WORDS_PER_PAGE} more</i>\n"
        text += "\n"

    text += _("vocab_tip", i18n)
    await send_safe_html(message, text)
