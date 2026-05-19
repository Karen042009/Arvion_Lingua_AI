"""
Grammar Guide — /grammar command with topic selection
Culture Corner — /culture command with topic selection
"""
import html
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.middlewares.localization import _, get_all_translations, Localization
from bot.states.app_states import AppStates
from bot.services.gemini_service import GeminiService
from bot.keyboards.reply import get_dynamic_reply_keyboard
from bot.utils.message_utils import send_safe_html
from config import SUPPORTED_LANGUAGES, LEARNING_LEVELS

locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
loc_middleware = Localization(locales_dir)
all_locales = loc_middleware.locales

culture_grammar_router = Router()
gemini_service = GeminiService()

# Grammar topics per language level
GRAMMAR_TOPICS = {
    "beginner": [
        "Present tense", "Articles (a/an/the)", "Plural nouns",
        "Basic pronouns", "Simple questions", "Negation",
    ],
    "intermediate": [
        "Past tense", "Future tense", "Conditional sentences",
        "Passive voice", "Relative clauses", "Modal verbs",
    ],
    "advanced": [
        "Subjunctive mood", "Perfect tenses", "Reported speech",
        "Inversion", "Cleft sentences", "Ellipsis",
    ],
}

CULTURE_TOPICS = [
    "Food & Cuisine", "Traditions & Festivals", "History",
    "Music & Arts", "Social Etiquette", "Famous Landmarks",
    "Language Curiosities", "Modern Culture",
]


# ─── Grammar Guide ────────────────────────────────────────────────────────────

@culture_grammar_router.message(Command("grammar"))
async def cmd_grammar(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, "i18n", {})
    if user_db.get("learning_mode") != "human":
        await message.answer(_("human_mode_only", i18n))
        return

    level_key = user_db.get("learning_level", "beginner")
    topics = GRAMMAR_TOPICS.get(level_key, GRAMMAR_TOPICS["beginner"])
    lang_name = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["display_name"]

    await state.set_state(AppStates.in_grammar_guide)
    await message.answer(
        _("grammar_guide_intro", i18n, lang=lang_name),
        reply_markup=get_dynamic_reply_keyboard(topics, i18n, "back_to_main_menu")
    )


@culture_grammar_router.message(AppStates.in_grammar_guide, F.text)
async def process_grammar_topic(message: Message, state: FSMContext, user_db: dict, bot: Bot):
    i18n = getattr(bot, "i18n", {})

    # Check if it's a valid grammar topic
    all_topics = sum(GRAMMAR_TOPICS.values(), [])
    if message.text not in all_topics:
        return

    processing_msg = await message.answer(_("generating_lesson", i18n))
    learning_lang = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["gemini_name"]
    native_lang = SUPPORTED_LANGUAGES[user_db["native_lang"]]["gemini_name"]
    level = LEARNING_LEVELS[user_db["learning_level"]]

    result = await gemini_service.get_grammar_lesson(message.text, learning_lang, native_lang, level)
    await processing_msg.delete()

    if not result:
        await message.answer(_("generation_error", i18n))
        return

    topic = html.escape(result.get("topic", message.text))
    rule = html.escape(result.get("rule", ""))
    examples = result.get("examples", [])
    translations = result.get("examples_translation", [])
    practice = result.get("practice", [])

    text = f"📚 <b>{topic}</b>\n\n"
    text += f"📖 <b>{_('grammar_rule', i18n)}:</b>\n{rule}\n\n"

    if examples:
        text += f"✏️ <b>{_('grammar_examples', i18n)}:</b>\n"
        for i, (ex, tr) in enumerate(zip(examples, translations), 1):
            text += f"  {i}. <i>{html.escape(ex)}</i>\n"
            text += f"     <code>{html.escape(tr)}</code>\n"

    if practice:
        text += f"\n🎯 <b>{_('grammar_practice', i18n)}:</b>\n"
        for p in practice[:2]:
            text += f"  • <i>{html.escape(p.get('sentence', ''))}</i>\n"
            text += f"    {html.escape(p.get('translation', ''))}\n"

    # Show topic list again for next lesson
    level_key = user_db.get("learning_level", "beginner")
    topics = GRAMMAR_TOPICS.get(level_key, GRAMMAR_TOPICS["beginner"])

    await send_safe_html(
        message, text,
        reply_markup=get_dynamic_reply_keyboard(topics, i18n, "back_to_main_menu")
    )


# ─── Culture Corner ───────────────────────────────────────────────────────────

@culture_grammar_router.message(Command("culture"))
async def cmd_culture(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, "i18n", {})
    if user_db.get("learning_mode") != "human":
        await message.answer(_("human_mode_only", i18n))
        return

    lang_name = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["display_name"]
    await state.set_state(AppStates.in_culture_corner)
    await message.answer(
        _("culture_intro", i18n, lang=lang_name),
        reply_markup=get_dynamic_reply_keyboard(CULTURE_TOPICS, i18n, "back_to_main_menu")
    )


@culture_grammar_router.message(AppStates.in_culture_corner, F.text)
async def process_culture_topic(message: Message, state: FSMContext, user_db: dict, bot: Bot):
    i18n = getattr(bot, "i18n", {})

    if message.text not in CULTURE_TOPICS:
        return

    processing_msg = await message.answer(_("generating_culture", i18n))
    learning_lang = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["gemini_name"]
    interface_lang = SUPPORTED_LANGUAGES[user_db["interface_lang"]]["gemini_name"]

    result = await gemini_service.get_culture_info(learning_lang, interface_lang, message.text)
    await processing_msg.delete()

    if not result:
        await message.answer(_("generation_error", i18n))
        return

    title = html.escape(result.get("title", message.text))
    content = html.escape(result.get("content", ""))
    fun_fact = html.escape(result.get("fun_fact", ""))
    tip = html.escape(result.get("tip", ""))

    text = (
        f"🌍 <b>{title}</b>\n\n"
        f"{content}\n\n"
        f"💡 <b>{_('fun_fact_label', i18n)}:</b> {fun_fact}\n\n"
        f"🗣 <b>{_('learner_tip', i18n)}:</b> <i>{tip}</i>"
    )

    await send_safe_html(
        message, text,
        reply_markup=get_dynamic_reply_keyboard(CULTURE_TOPICS, i18n, "back_to_main_menu")
    )
