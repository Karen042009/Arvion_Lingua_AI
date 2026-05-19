"""
Game-based learning features:
  - Word Scramble  🔀
  - Hangman        🎯
  - Speed Round    ⚡
"""
import html
import random
import asyncio
import logging
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.middlewares.localization import _, get_all_translations, Localization
from bot.states.app_states import AppStates
from bot.services.gemini_service import GeminiService
from bot.keyboards.reply import get_dynamic_reply_keyboard
from bot.utils.message_utils import send_safe_html
from database.db_utils import increment_user_stat, get_or_create_user
from config import SUPPORTED_LANGUAGES, LEARNING_LEVELS

locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
loc_middleware = Localization(locales_dir)
all_locales = loc_middleware.locales

games_router = Router()
gemini_service = GeminiService()

HANGMAN_STAGES = [
    "```\n  +---+\n  |   |\n      |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n      |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n  |   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|   |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n      |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n /    |\n      |\n=========```",
    "```\n  +---+\n  |   |\n  O   |\n /|\\  |\n / \\  |\n      |\n=========```",
]
MAX_WRONG = len(HANGMAN_STAGES) - 1


# ─── Helpers ─────────────────────────────────────────────────────────────────

def scramble_word(word: str) -> str:
    """Scramble a word ensuring it's different from original."""
    letters = list(word.upper())
    for _ in range(10):
        random.shuffle(letters)
        if "".join(letters) != word.upper():
            break
    return "".join(letters)


def build_hangman_display(word: str, guessed: set) -> str:
    return " ".join(
        f"<b>{c.upper()}</b>" if c.upper() in guessed else "＿"
        for c in word
    )


# ─── Word Scramble ────────────────────────────────────────────────────────────

@games_router.message(
    AppStates.in_learning_menu,
    F.text.in_(get_all_translations("scramble_button", all_locales))
)
async def handle_scramble_start(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    if user_db.get("learning_mode") != "human":
        await message.answer(_("human_mode_only", i18n))
        return
    await _start_scramble_round(message, user_db, state, i18n)


async def _start_scramble_round(message, user_db, state, i18n):
    processing_msg = await message.answer(_("generating_scramble", i18n))
    learning_lang = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["gemini_name"]
    native_lang = SUPPORTED_LANGUAGES[user_db["native_lang"]]["gemini_name"]
    level = LEARNING_LEVELS[user_db["learning_level"]]

    result = await gemini_service.get_word_for_scramble(learning_lang, native_lang, level)
    await processing_msg.delete()

    if not result or not result.get("word"):
        await message.answer(_("generation_error", i18n))
        user_db_fresh = await get_or_create_user(message.from_user.id)
        from bot.handlers.learning_handlers import show_learning_menu
        await show_learning_menu(message, i18n, user_db_fresh, state)
        return

    word = result["word"].upper().strip()
    # Keep only alpha chars for scramble
    word = "".join(c for c in word if c.isalpha())
    if len(word) < 3:
        await message.answer(_("generation_error", i18n))
        return

    scrambled = scramble_word(word)
    translation = html.escape(result.get("translation", ""))
    hint = html.escape(result.get("hint", ""))

    await state.set_state(AppStates.awaiting_scramble_answer)
    await state.update_data(
        scramble_word=word,
        scramble_attempts=0,
    )

    text = (
        f"🔀 <b>{_('scramble_title', i18n)}</b>\n\n"
        f"<b>{_('scramble_hint', i18n)}:</b> {hint}\n"
        f"<b>{_('translation', i18n)}:</b> {translation}\n\n"
        f"🔡 <code>{scrambled}</code>\n\n"
        f"<i>{_('scramble_prompt', i18n)}</i>"
    )
    await message.answer(
        text,
        reply_markup=get_dynamic_reply_keyboard(
            [_("scramble_give_up", i18n)], i18n, "back_to_learn_menu"
        )
    )


@games_router.message(AppStates.awaiting_scramble_answer, F.text)
async def process_scramble_answer(message: Message, state: FSMContext, user_db: dict, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    data = await state.get_data()
    word = data.get("scramble_word", "")
    attempts = data.get("scramble_attempts", 0)

    give_up_texts = get_all_translations("scramble_give_up", all_locales)
    if message.text in give_up_texts:
        await message.answer(
            _("scramble_gave_up", i18n, word=word),
            reply_markup=get_dynamic_reply_keyboard(
                [_("scramble_button", i18n)], i18n, "back_to_learn_menu"
            )
        )
        await state.set_state(AppStates.in_learning_menu)
        return

    user_answer = message.text.upper().strip()
    attempts += 1
    await state.update_data(scramble_attempts=attempts)

    if user_answer == word:
        await increment_user_stat(message.from_user.id, "words_learned_count")
        stars = "⭐⭐⭐" if attempts == 1 else "⭐⭐" if attempts <= 3 else "⭐"
        text = (
            f"🎉 {stars} <b>{_('scramble_correct', i18n)}</b>\n"
            f"✅ <code>{word}</code>\n"
            f"<i>{_('attempts', i18n, count=attempts)}</i>"
        )
        await message.answer(
            text,
            reply_markup=get_dynamic_reply_keyboard(
                [_("scramble_button", i18n)], i18n, "back_to_learn_menu"
            )
        )
        await state.set_state(AppStates.in_learning_menu)
    else:
        await message.answer(
            _("scramble_wrong", i18n, attempts=attempts),
            reply_markup=get_dynamic_reply_keyboard(
                [_("scramble_give_up", i18n)], i18n, "back_to_learn_menu"
            )
        )


# ─── Hangman ──────────────────────────────────────────────────────────────────

@games_router.message(
    AppStates.in_learning_menu,
    F.text.in_(get_all_translations("hangman_button", all_locales))
)
async def handle_hangman_start(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    if user_db.get("learning_mode") != "human":
        await message.answer(_("human_mode_only", i18n))
        return
    await _start_hangman_round(message, user_db, state, i18n)


async def _start_hangman_round(message, user_db, state, i18n):
    processing_msg = await message.answer(_("generating_hangman", i18n))
    learning_lang = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["gemini_name"]
    native_lang = SUPPORTED_LANGUAGES[user_db["native_lang"]]["gemini_name"]
    level = LEARNING_LEVELS[user_db["learning_level"]]

    result = await gemini_service.get_word_for_hangman(learning_lang, native_lang, level)
    await processing_msg.delete()

    if not result or not result.get("word"):
        await message.answer(_("generation_error", i18n))
        return

    word = "".join(c for c in result["word"].upper() if c.isalpha())
    if len(word) < 3:
        await message.answer(_("generation_error", i18n))
        return

    translation = html.escape(result.get("translation", ""))
    category = html.escape(result.get("category", ""))

    await state.set_state(AppStates.in_hangman)
    await state.update_data(
        hangman_word=word,
        hangman_guessed=[],
        hangman_wrong=0,
        hangman_translation=translation,
    )

    display = build_hangman_display(word, set())
    text = (
        f"🎯 <b>{_('hangman_title', i18n)}</b>\n\n"
        f"{HANGMAN_STAGES[0]}\n\n"
        f"<b>{_('category', i18n)}:</b> {category}\n"
        f"<b>{_('translation', i18n)}:</b> {translation}\n\n"
        f"{display}\n\n"
        f"<i>{_('hangman_prompt', i18n, wrong=0, max=MAX_WRONG)}</i>"
    )
    await send_safe_html(
        message, text,
        reply_markup=get_dynamic_reply_keyboard(
            [_("hangman_give_up", i18n)], i18n, "back_to_learn_menu"
        )
    )


@games_router.message(AppStates.in_hangman, F.text)
async def process_hangman_letter(message: Message, state: FSMContext, user_db: dict, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    data = await state.get_data()
    word = data.get("hangman_word", "")
    guessed = set(data.get("hangman_guessed", []))
    wrong = data.get("hangman_wrong", 0)
    translation = data.get("hangman_translation", "")

    give_up_texts = get_all_translations("hangman_give_up", all_locales)
    if message.text in give_up_texts:
        await message.answer(
            _("hangman_gave_up", i18n, word=word),
            reply_markup=get_dynamic_reply_keyboard(
                [_("hangman_button", i18n)], i18n, "back_to_learn_menu"
            )
        )
        await state.set_state(AppStates.in_learning_menu)
        return

    letter = message.text.upper().strip()

    # Validate input
    if len(letter) != 1 or not letter.isalpha():
        await message.answer(_("hangman_one_letter", i18n))
        return

    if letter in guessed:
        await message.answer(_("hangman_already_guessed", i18n, letter=letter))
        return

    guessed.add(letter)

    if letter in word:
        # Correct guess
        display = build_hangman_display(word, guessed)
        # Check win
        if all(c in guessed for c in word):
            await increment_user_stat(message.from_user.id, "words_learned_count")
            text = (
                f"🎉 <b>{_('hangman_won', i18n)}</b>\n\n"
                f"✅ <code>{word}</code> — {translation}"
            )
            await message.answer(
                text,
                reply_markup=get_dynamic_reply_keyboard(
                    [_("hangman_button", i18n)], i18n, "back_to_learn_menu"
                )
            )
            await state.set_state(AppStates.in_learning_menu)
            return

        await state.update_data(hangman_guessed=list(guessed))
        guessed_str = " ".join(sorted(guessed))
        text = (
            f"✅ <b>{letter}</b> — {_('hangman_good_guess', i18n)}\n\n"
            f"{HANGMAN_STAGES[wrong]}\n\n"
            f"{display}\n\n"
            f"<i>{_('hangman_guessed_letters', i18n)}: {guessed_str}</i>\n"
            f"<i>{_('hangman_prompt', i18n, wrong=wrong, max=MAX_WRONG)}</i>"
        )
    else:
        # Wrong guess
        wrong += 1
        await state.update_data(hangman_guessed=list(guessed), hangman_wrong=wrong)

        if wrong >= MAX_WRONG:
            text = (
                f"💀 <b>{_('hangman_lost', i18n)}</b>\n\n"
                f"{HANGMAN_STAGES[MAX_WRONG]}\n\n"
                f"✅ {_('the_word_was', i18n)}: <code>{word}</code> — {translation}"
            )
            await send_safe_html(
                message, text,
                reply_markup=get_dynamic_reply_keyboard(
                    [_("hangman_button", i18n)], i18n, "back_to_learn_menu"
                )
            )
            await state.set_state(AppStates.in_learning_menu)
            return

        display = build_hangman_display(word, guessed)
        guessed_str = " ".join(sorted(guessed))
        text = (
            f"❌ <b>{letter}</b> — {_('hangman_wrong_guess', i18n)}\n\n"
            f"{HANGMAN_STAGES[wrong]}\n\n"
            f"{display}\n\n"
            f"<i>{_('hangman_guessed_letters', i18n)}: {guessed_str}</i>\n"
            f"<i>{_('hangman_prompt', i18n, wrong=wrong, max=MAX_WRONG)}</i>"
        )

    await send_safe_html(
        message, text,
        reply_markup=get_dynamic_reply_keyboard(
            [_("hangman_give_up", i18n)], i18n, "back_to_learn_menu"
        )
    )


# ─── Speed Round ──────────────────────────────────────────────────────────────

SPEED_ROUND_SECONDS = 30


@games_router.message(
    AppStates.in_learning_menu,
    F.text.in_(get_all_translations("speed_round_button", all_locales))
)
async def handle_speed_round_start(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    if user_db.get("learning_mode") != "human":
        await message.answer(_("human_mode_only", i18n))
        return

    processing_msg = await message.answer(_("generating_speed_round", i18n))
    learning_lang = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["gemini_name"]
    native_lang = SUPPORTED_LANGUAGES[user_db["native_lang"]]["gemini_name"]
    level = LEARNING_LEVELS[user_db["learning_level"]]

    words = await gemini_service.get_speed_round_words(learning_lang, native_lang, level, count=8)
    await processing_msg.delete()

    if not words or len(words) < 2:
        await message.answer(_("generation_error", i18n))
        return

    await state.set_state(AppStates.in_speed_round)
    await state.update_data(
        speed_words=words,
        speed_index=0,
        speed_correct=0,
        speed_total=len(words),
        speed_start_time=asyncio.get_event_loop().time(),
    )

    await message.answer(
        _("speed_round_intro", i18n, count=len(words), seconds=SPEED_ROUND_SECONDS),
        reply_markup=get_dynamic_reply_keyboard(
            [_("speed_start", i18n)], i18n, "back_to_learn_menu"
        )
    )


@games_router.message(AppStates.in_speed_round, F.text)
async def handle_speed_round_start_button(message: Message, state: FSMContext, bot: Bot, user_db: dict):
    i18n = getattr(bot, "i18n", {})
    start_texts = get_all_translations("speed_start", all_locales)
    if message.text not in start_texts:
        return

    await state.set_state(AppStates.awaiting_speed_answer)
    await state.update_data(speed_start_time=asyncio.get_event_loop().time())
    await _show_speed_word(message, i18n, state)


async def _show_speed_word(message, i18n, state):
    data = await state.get_data()
    words = data.get("speed_words", [])
    index = data.get("speed_index", 0)
    correct = data.get("speed_correct", 0)
    total = data.get("speed_total", len(words))
    start_time = data.get("speed_start_time", asyncio.get_event_loop().time())

    elapsed = asyncio.get_event_loop().time() - start_time
    remaining = max(0, SPEED_ROUND_SECONDS - int(elapsed))

    if index >= len(words) or remaining <= 0:
        # Game over
        await _end_speed_round(message, i18n, state, correct, total, timed_out=(remaining <= 0))
        return

    word_data = words[index]
    word = html.escape(word_data.get("word", ""))

    text = (
        f"⚡ <b>{_('speed_round_title', i18n)}</b>  "
        f"⏱ {remaining}s  |  {index + 1}/{total}\n\n"
        f"<b>{word}</b>\n\n"
        f"<i>{_('speed_translate_prompt', i18n)}</i>"
    )
    await message.answer(
        text,
        reply_markup=get_dynamic_reply_keyboard(
            [_("speed_skip", i18n)], i18n, "back_to_learn_menu"
        )
    )


@games_router.message(AppStates.awaiting_speed_answer, F.text)
async def process_speed_answer(message: Message, state: FSMContext, bot: Bot, user_db: dict):
    i18n = getattr(bot, "i18n", {})
    data = await state.get_data()
    words = data.get("speed_words", [])
    index = data.get("speed_index", 0)
    correct = data.get("speed_correct", 0)
    start_time = data.get("speed_start_time", asyncio.get_event_loop().time())

    elapsed = asyncio.get_event_loop().time() - start_time
    remaining = max(0, SPEED_ROUND_SECONDS - int(elapsed))

    if remaining <= 0:
        await _end_speed_round(message, i18n, state, correct, len(words), timed_out=True)
        return

    skip_texts = get_all_translations("speed_skip", all_locales)
    if message.text in skip_texts:
        await state.update_data(speed_index=index + 1)
        await _show_speed_word(message, i18n, state)
        return

    if index >= len(words):
        await _end_speed_round(message, i18n, state, correct, len(words), timed_out=False)
        return

    word_data = words[index]
    correct_translation = word_data.get("translation", "").strip().lower()
    user_answer = message.text.strip().lower()

    # Fuzzy match — accept if answer contains or is contained in correct translation
    is_correct = (
        user_answer == correct_translation or
        user_answer in correct_translation or
        correct_translation in user_answer
    )

    if is_correct:
        correct += 1
        feedback = f"✅"
    else:
        feedback = f"❌ → <b>{html.escape(word_data.get('translation', ''))}</b>"

    await state.update_data(speed_index=index + 1, speed_correct=correct)
    await message.answer(feedback)
    await _show_speed_word(message, i18n, state)


async def _end_speed_round(message, i18n, state, correct, total, timed_out):
    if correct > 0:
        from database.db_utils import increment_user_stat
        for _ in range(correct):
            await increment_user_stat(message.from_user.id, "words_learned_count")

    accuracy = int((correct / total * 100)) if total > 0 else 0
    stars = "⭐⭐⭐" if accuracy >= 80 else "⭐⭐" if accuracy >= 50 else "⭐"

    timeout_text = f"\n⏱ {i18n.get('speed_time_up', 'Time up!')}" if timed_out else ""
    text = (
        f"{'⏱' if timed_out else '🏁'} <b>{_('speed_round_done', i18n)}</b>{timeout_text}\n\n"
        f"{stars}\n"
        f"✅ {correct}/{total} {_('correct_answers', i18n)}\n"
        f"📊 {accuracy}% {_('accuracy', i18n)}"
    )
    await message.answer(
        text,
        reply_markup=get_dynamic_reply_keyboard(
            [_("speed_round_button", i18n)], i18n, "back_to_learn_menu"
        )
    )
    await state.set_state(AppStates.in_learning_menu)
