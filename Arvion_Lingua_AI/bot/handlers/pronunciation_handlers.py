"""
Pronunciation scoring feature.
User sends a voice message with a word → bot scores accuracy vs target word.
Triggered from learning flow when a word is shown.
"""
import io
import logging
import html
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.middlewares.localization import _
from bot.services.gemini_service import GeminiService
from bot.states.app_states import AppStates
from bot.keyboards.reply import get_dynamic_reply_keyboard
from bot.utils.message_utils import send_safe_html

pronunciation_router = Router()
gemini_service = GeminiService()


async def start_pronunciation_practice(
    message: Message,
    i18n: dict,
    state: FSMContext,
    word: str,
    language: str,
):
    """Called from learning flow to start pronunciation practice for a word."""
    await state.set_state(AppStates.awaiting_pronunciation)
    await state.update_data(pronunciation_word=word, pronunciation_lang=language)
    await message.answer(
        _("pronunciation_prompt", i18n, word=html.escape(word)),
        reply_markup=get_dynamic_reply_keyboard([], i18n, "back_to_learn_menu"),
    )


@pronunciation_router.message(AppStates.awaiting_pronunciation, F.voice)
async def process_pronunciation_voice(message: Message, state: FSMContext, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    data = await state.get_data()
    target_word = data.get("pronunciation_word", "")
    language = data.get("pronunciation_lang", "English")

    processing_msg = await message.answer("🎤 " + _("analyzing_pronunciation", i18n))

    try:
        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        voice_buffer = io.BytesIO()
        await bot.download_file(file_info.file_path, voice_buffer)
        voice_data = voice_buffer.getvalue()

        transcribed = await gemini_service.transcribe_audio(voice_data)
        if not transcribed:
            await processing_msg.edit_text(_("could_not_understand_audio", i18n))
            return

        result = await gemini_service.score_pronunciation(target_word, transcribed, language)
        await processing_msg.delete()

        if not result:
            await message.answer(_("generation_error", i18n))
            return

        score = result.get("score", 0)
        feedback = html.escape(result.get("feedback", ""))
        correct = result.get("correct", False)

        # Score emoji
        if score >= 90:
            score_emoji = "🏆"
        elif score >= 70:
            score_emoji = "✅"
        elif score >= 50:
            score_emoji = "⚠️"
        else:
            score_emoji = "❌"

        # Progress bar
        filled = min(int(score / 10), 10)
        bar = "█" * filled + "░" * (10 - filled)

        text = (
            f"{score_emoji} <b>{_('pronunciation_result', i18n)}</b>\n\n"
            f"🎯 <b>{_('target_word', i18n)}:</b> <code>{html.escape(target_word)}</code>\n"
            f"🎤 <b>{_('you_said', i18n)}:</b> <i>{html.escape(transcribed)}</i>\n\n"
            f"📊 <b>{_('accuracy', i18n)}:</b> {score}/100\n"
            f"   {bar}\n\n"
            f"💬 {feedback}"
        )

        buttons = [_("try_again", i18n)]
        await send_safe_html(
            message, text,
            reply_markup=get_dynamic_reply_keyboard(buttons, i18n, "back_to_learn_menu")
        )

    except Exception as e:
        logging.error(f"Pronunciation error: {e}")
        await processing_msg.edit_text(_("voice_error", i18n))


@pronunciation_router.message(AppStates.awaiting_pronunciation, F.text)
async def handle_pronunciation_text(message: Message, state: FSMContext, bot: Bot):
    """Handle 'Try Again' button or any text in pronunciation state."""
    i18n = getattr(bot, "i18n", {})
    try_again_texts = [i18n.get("try_again", "🔄 Try Again")]
    data = await state.get_data()
    word = data.get("pronunciation_word", "")
    lang = data.get("pronunciation_lang", "English")

    if message.text in try_again_texts:
        await message.answer(
            _("pronunciation_prompt", i18n, word=html.escape(word)),
            reply_markup=get_dynamic_reply_keyboard([], i18n, "back_to_learn_menu"),
        )
    else:
        # Back button or unknown — go to learn menu
        from bot.handlers.learning_handlers import show_learning_menu
        from database.db_utils import get_or_create_user
        user_db = await get_or_create_user(message.from_user.id)
        await show_learning_menu(message, i18n, user_db, state)
