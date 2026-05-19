import html
from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, BotCommand
from bot.middlewares.localization import _
from bot.keyboards.reply import get_main_reply_keyboard
from bot.states.app_states import AppStates
from bot.services.gemini_service import GeminiService
from database.db_utils import (
    increment_user_stat, get_saved_words_count,
    check_and_unlock_badges, update_username, get_or_create_user,
    update_daily_challenge_progress
)
from config import SUPPORTED_LANGUAGES, SUPPORTED_PROGRAMMING_LANGUAGES

common_router = Router()
gemini_service = GeminiService()


async def notify_badges(message: Message, i18n: dict, user_db: dict):
    """Check and notify user about newly unlocked badges."""
    new_badges = await check_and_unlock_badges(message.from_user.id, user_db)
    for badge in new_badges:
        await message.answer(f"🏅 <b>{_('badge_unlocked', i18n)}</b> {badge}")


async def navigate_to_main_menu(message: Message, i18n: dict, state: FSMContext):
    await state.clear()
    await state.set_state(AppStates.idle)
    await message.answer(
        _('main_menu_text', i18n),
        reply_markup=get_main_reply_keyboard(i18n)
    )

@common_router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await message.answer(_('welcome', i18n))
    await navigate_to_main_menu(message, i18n, state)

@common_router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await navigate_to_main_menu(message, i18n, state)

@common_router.message(F.text.in_([
    "⬅️ Back to Menu", "⬅️ В главное меню", "⬅️ Գլխավոր մենյու", "⬅️ Volver",
    "⬅️ Retour", "⬅️ Zurück zum Menü", "⬅️ Indietro", "⬅️ 返回",
    "⬅️ 戻る", "⬅️ 뒤로", "⬅️ वापस", "⬅️ Voltar", "⬅️ رجوع"
]))
async def handle_back_to_main_menu(message: Message, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await navigate_to_main_menu(message, i18n, state)

@common_router.message(Command("stats"))
async def cmd_stats(message: Message, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    streak = user_db.get('streak_count', 0)
    translations = user_db.get('translations_count', 0)
    concepts = user_db.get('words_learned_count', 0)
    quizzes = user_db.get('quizzes_passed_count', 0)
    facts = user_db.get('facts_requested_count', 0)
    vocab_count = await get_saved_words_count(message.from_user.id)

    def progress_bar(value: int, max_val: int = 50, length: int = 10) -> str:
        filled = min(int((value / max_val) * length), length)
        return "█" * filled + "░" * (length - filled)

    streak_text = _('streak_text', i18n, count=streak) if streak > 0 else ""

    # Milestone badges
    badges = []
    if translations >= 10:
        badges.append("🌐 Translator")
    if concepts >= 20:
        badges.append("📚 Word Master")
    if quizzes >= 10:
        badges.append("🧩 Quiz Champion")
    if streak >= 7:
        badges.append("🔥 Week Streak")
    if streak >= 30:
        badges.append("⚡ Month Streak")
    badges_text = "  ".join(badges) if badges else _("no_badges_yet", i18n)

    text = (
        _('stats_header', i18n) +
        f"🌐 <b>{_('stat_translations', i18n)}:</b> {translations}\n"
        f"   {progress_bar(translations)} {translations}/50\n\n"
        f"📝 <b>{_('stat_words', i18n)}:</b> {concepts}\n"
        f"   {progress_bar(concepts)} {concepts}/50\n\n"
        f"🧩 <b>{_('stat_quizzes', i18n)}:</b> {quizzes}\n"
        f"   {progress_bar(quizzes)} {quizzes}/50\n\n"
        f"💡 <b>{_('stat_facts', i18n)}:</b> {facts}\n\n"
        f"💾 <b>{_('stat_vocab', i18n)}:</b> {vocab_count}\n\n"
        f"🏅 <b>{_('stat_badges', i18n)}:</b> {badges_text}"
        + streak_text
    )
    await message.answer(text)

@common_router.message(Command("fact"))
async def cmd_fact(message: Message, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    processing_msg = await message.answer("🤔...")

    mode = user_db.get('learning_mode', 'human')
    interface_lang = SUPPORTED_LANGUAGES[user_db['interface_lang']]['gemini_name']

    if mode == 'human':
        subject = SUPPORTED_LANGUAGES[user_db['learning_lang']]['gemini_name']
    else:
        subject = SUPPORTED_PROGRAMMING_LANGUAGES[
            user_db['programming_lang']
        ]['display_name']

    fact = await gemini_service.get_fun_fact(mode, subject, interface_lang)

    await processing_msg.delete()
    if fact:
        await message.answer(_('fun_fact_text', i18n, subject=subject, fact=html.escape(fact)))
        await increment_user_stat(message.from_user.id, 'facts_requested_count')
    else:
        await message.answer(_('generation_error', i18n))

@common_router.message(Command("models"))
async def cmd_models(message: Message, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    interface_lang = user_db.get('interface_lang', 'en')
    
    ranked = gemini_service.ranked_models
    if not ranked:
        await message.answer("⚠️ No active Gemini models found.")
        return
        
    if interface_lang == 'hy':
        title = "<b>🏆 Gemini Մոդելների Ավտոմատ Դասակարգում և Fallback</b>"
        desc = "Բոտը դինամիկ կերպով դասակարգում է հասանելի Gemini մոդելները և ավտոմատ անցնում հաջորդ լավագույնին՝ սխալների կամ սահմանաչափերի (rate limits) դեպքում:"
        queue_header = "<b>Մոդելների առաջնահերթության հերթը՝</b>"
        active_label = "Ակտիվ"
        status_label = "🔄 Կարգավիճակ՝ Լիովին գործունակ (Ավտոմատ Fallback-ը միացված է)"
    else:
        title = "<b>🏆 Gemini Auto-Ranking & Fallback Status</b>"
        desc = "The bot dynamically ranks available models and automatically switches to the next best one if any rate-limit or API failure occurs."
        queue_header = "<b>Model Priority Queue:</b>"
        active_label = "Active"
        status_label = "🔄 Status: Fully Operational (Auto-Fallback Enabled)"

    response = f"{title}\n\n{desc}\n\n{queue_header}\n"
    
    for idx, model in enumerate(ranked, 1):
        prefix = "🥇" if idx == 1 else f"{idx}."
        active_status = f" (<i>{active_label}</i>)" if idx == 1 else ""
        response += f"{prefix} <code>{model}</code>{active_status}\n"
        
    response += f"\n{status_label}"
    
    from bot.utils.message_utils import send_safe_html
    await send_safe_html(message, response)


@common_router.message(Command("help"))
async def cmd_help(message: Message, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    await message.answer(_("help_text", i18n))