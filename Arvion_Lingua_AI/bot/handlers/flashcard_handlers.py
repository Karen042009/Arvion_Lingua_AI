"""
Flashcard review with SM-2 spaced repetition algorithm.
/review command — shows words due for review.
User translates the word, rates difficulty, SM-2 schedules next review.
"""
import html
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

from bot.middlewares.localization import _
from bot.services.gemini_service import GeminiService
from bot.states.app_states import AppStates
from bot.keyboards.reply import get_dynamic_reply_keyboard
from bot.utils.message_utils import send_safe_html
from database.db_utils import (
    get_words_due_for_review, update_word_review, get_saved_words_count
)

flashcard_router = Router()
gemini_service = GeminiService()


async def show_next_flashcard(message: Message, i18n: dict, state: FSMContext):
    user_id = message.from_user.id
    words = await get_words_due_for_review(user_id, limit=1)

    if not words:
        total = await get_saved_words_count(user_id)
        if total == 0:
            await message.answer(
                _("vocab_empty", i18n),
                reply_markup=get_dynamic_reply_keyboard([], i18n, "back_to_main_menu")
            )
        else:
            await message.answer(
                _("review_all_done", i18n),
                reply_markup=get_dynamic_reply_keyboard([], i18n, "back_to_main_menu")
            )
        await state.clear()
        return

    word_data = words[0]
    await state.set_state(AppStates.awaiting_flashcard_answer)
    await state.update_data(
        flashcard_id=word_data["id"],
        flashcard_word=word_data["word"],
        flashcard_translation=word_data["translation"],
        flashcard_language=word_data["language"],
        flashcard_review_count=word_data.get("review_count", 0),
    )

    review_count = word_data.get("review_count", 0)
    interval = word_data.get("interval_days", 1)

    text = (
        f"🃏 <b>{_('flashcard_title', i18n)}</b>\n\n"
        f"<b>{html.escape(word_data['word'])}</b>\n"
        f"<i>({html.escape(word_data['language'])})</i>\n\n"
        f"{_('flashcard_translate_prompt', i18n)}\n\n"
        f"<i>📅 {_('review_interval', i18n, days=interval)} · "
        f"🔁 {_('review_count_label', i18n, count=review_count)}</i>"
    )

    await message.answer(
        text,
        reply_markup=get_dynamic_reply_keyboard(
            [_("show_answer", i18n)], i18n, "back_to_main_menu"
        )
    )


@flashcard_router.message(Command("review"))
async def cmd_review(message: Message, state: FSMContext):
    i18n = getattr(message.bot, "i18n", {})
    await state.clear()
    await state.set_state(AppStates.in_flashcard_review)

    total = await get_saved_words_count(message.from_user.id)
    due = await get_words_due_for_review(message.from_user.id, limit=50)

    await message.answer(
        _("review_intro", i18n, total=total, due=len(due)),
        reply_markup=get_dynamic_reply_keyboard(
            [_("start_review", i18n)], i18n, "back_to_main_menu"
        )
    )


@flashcard_router.message(AppStates.in_flashcard_review, F.text)
async def start_review_session(message: Message, state: FSMContext, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    start_texts = [i18n.get("start_review", "▶️ Start Review")]
    if message.text in start_texts:
        await show_next_flashcard(message, i18n, state)


@flashcard_router.message(AppStates.awaiting_flashcard_answer, F.text)
async def process_flashcard_answer(message: Message, state: FSMContext, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    data = await state.get_data()

    word_id = data.get("flashcard_id")
    word = data.get("flashcard_word", "")
    correct_translation = data.get("flashcard_translation", "")
    language = data.get("flashcard_language", "")

    show_answer_texts = [i18n.get("show_answer", "👁 Show Answer")]

    # "Show Answer" button — reveal without scoring
    if message.text in show_answer_texts:
        text = (
            f"📖 <b>{html.escape(word)}</b>\n"
            f"✅ {html.escape(correct_translation)}\n\n"
            f"{_('rate_difficulty', i18n)}"
        )
        rating_kb = ReplyKeyboardMarkup(
            keyboard=[
                [
                    KeyboardButton(text="😰 " + _("rating_hard", i18n)),
                    KeyboardButton(text="🤔 " + _("rating_ok", i18n)),
                    KeyboardButton(text="😊 " + _("rating_easy", i18n)),
                ]
            ],
            resize_keyboard=True,
            one_time_keyboard=True,
        )
        await state.update_data(showing_answer=True)
        await message.answer(text, reply_markup=rating_kb)
        return

    # Rating buttons
    hard_texts = ["😰 " + i18n.get("rating_hard", "Hard")]
    ok_texts = ["🤔 " + i18n.get("rating_ok", "OK")]
    easy_texts = ["😊 " + i18n.get("rating_easy", "Easy")]

    quality = None
    if message.text in hard_texts:
        quality = 1
    elif message.text in ok_texts:
        quality = 3
    elif message.text in easy_texts:
        quality = 5

    if quality is not None and word_id:
        await update_word_review(message.from_user.id, word_id, quality)
        await show_next_flashcard(message, i18n, state)
        return

    # User typed a translation — evaluate it
    user_answer = message.text
    is_correct = user_answer.strip().lower() == correct_translation.strip().lower()

    if is_correct:
        quality = 5
        result_text = f"✅ <b>{_('correct', i18n)}</b> — {html.escape(correct_translation)}"
    else:
        quality = 2
        # Use AI for fuzzy evaluation
        feedback = await gemini_service.evaluate_user_answer(
            original_text=word,
            user_translation=user_answer,
            source_lang=language,
            target_lang="English"
        )
        result_text = (
            f"❌ <b>{_('incorrect', i18n)}</b>\n"
            f"✅ {html.escape(correct_translation)}\n\n"
            f"💬 {html.escape(feedback or '')}"
        )

    await update_word_review(message.from_user.id, word_id, quality)
    await send_safe_html(message, result_text)
    await show_next_flashcard(message, i18n, state)
