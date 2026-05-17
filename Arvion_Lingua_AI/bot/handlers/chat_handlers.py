from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from pathlib import Path
from bot.middlewares.localization import _, get_all_translations, Localization
from bot.states.app_states import AppStates
from bot.services.gemini_service import GeminiService
from bot.services.tts_service import text_to_speech_file
from database.db_utils import clear_chat_history, add_to_chat_history
from bot.utils.message_utils import send_safe_html
from bot.keyboards.reply import get_dynamic_reply_keyboard
from config import SUPPORTED_LANGUAGES, SUPPORTED_PROGRAMMING_LANGUAGES

chat_router = Router()
gemini_service = GeminiService()

# --- Load locales for static text filters (similar to translate_handlers) ---
locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
loc_middleware = Localization(locales_dir)
all_locales = loc_middleware.locales


async def show_chat_mode_selection(message: Message, i18n: dict, state: FSMContext):
    await state.set_state(AppStates.in_chat_menu)
    buttons = [i18n.get("chat_mode_regular"), i18n.get("chat_mode_roleplay")]
    await message.answer(
        _("select_chat_mode", i18n),
        reply_markup=get_dynamic_reply_keyboard(buttons, i18n, "back_to_main_menu"),
    )


async def cb_chat_entry(message: Message, state: FSMContext):
    i18n = getattr(message.bot, "i18n", {})
    await state.clear()
    await state.set_state(AppStates.in_chat)
    await message.answer(
        _("chat_prompt", i18n),
        reply_markup=get_dynamic_reply_keyboard([], i18n, "back_to_main_menu"),
    )


@chat_router.message(AppStates.in_chat_menu)
async def process_chat_menu_choice(
    message: Message, i18n: dict, state: FSMContext, bot
):
    locales = bot.loc_middleware.locales
    choice = message.text

    if choice in get_all_translations("chat_mode_regular", locales):
        await state.set_state(AppStates.in_chat)
        await message.answer(
            _("chat_prompt", i18n),
            reply_markup=get_dynamic_reply_keyboard([], i18n, "back_to_chat_modes"),
        )

    elif choice in get_all_translations("chat_mode_roleplay", locales):
        await state.set_state(AppStates.awaiting_roleplay_scenario)
        scenarios = [
            i18n.get("roleplay_cafe"),
            i18n.get("roleplay_hotel"),
            i18n.get("roleplay_job_interview"),
        ]
        await message.answer(
            _("select_roleplay_scenario", i18n),
            reply_markup=get_dynamic_reply_keyboard(
                scenarios, i18n, "back_to_chat_modes"
            ),
        )


@chat_router.message(
    F.text.in_(get_all_translations("back_to_chat_modes", all_locales))
)
async def handle_back_to_chat_menu(message: Message, state: FSMContext):
    i18n = getattr(message.bot, "i18n", {})
    await show_chat_mode_selection(message, i18n, state)


@chat_router.message(AppStates.awaiting_roleplay_scenario)
async def process_roleplay_scenario(
    message: Message, user_db: dict, state: FSMContext, bot
):
    i18n = getattr(bot, "i18n", {})
    locales = bot.loc_middleware.locales
    choice = message.text

    scenario_map = {
        "roleplay_cafe": "cafe",
        "roleplay_hotel": "hotel",
        "roleplay_job_interview": "job_interview",
    }

    scenario_key = None
    for key, text_func in scenario_map.items():
        if choice in get_all_translations(key, locales):
            scenario_key = text_func
            break

    if not scenario_key:
        return

    mode = user_db.get("learning_mode", "human")
    if mode == "human":
        lang = SUPPORTED_LANGUAGES[user_db["learning_lang"]]["gemini_name"]
    else:
        lang = SUPPORTED_PROGRAMMING_LANGUAGES[user_db["programming_lang"]][
            "display_name"
        ]

    persona_prompt = _(f"persona_{scenario_key}", i18n, lang=lang)
    await clear_chat_history(message.from_user.id)
    await gemini_service.chat_with_ai(
        message.from_user.id, "Hello, let's start!", persona=persona_prompt
    )

    await state.set_state(AppStates.in_roleplay)
    await state.update_data(persona=persona_prompt)
    await message.answer(
        _("roleplay_started", i18n),
        reply_markup=get_dynamic_reply_keyboard([], i18n, "back_to_chat_modes"),
    )


@chat_router.message(AppStates.in_chat, F.text, ~Command(commands=["menu", "reset"]))
@chat_router.message(
    AppStates.in_roleplay, F.text, ~Command(commands=["menu", "reset"])
)
async def process_chat_message(message: Message, state: FSMContext):
    fsm_data = await state.get_data()
    persona = fsm_data.get("persona")

    # Intercept creator/trainer questions and answer with a fixed name
    text_lc = (message.text or "").lower()
    creator_patterns = [
        # English
        "who created you",
        "who made you",
        "who built you",
        "who trained you",
        "who trained the model",
        "who is your creator",
        "your creator",
        # Armenian
        "ով է քեզ ստեղծել",
        "ով ա քեզ ստեղծել",
        "ով է ստեղծել",
        "ով ա ստեղծել",
        "ով է քո ստեղծողը",
        "քո ստեղծողը ով է",
        "ով է մարզել քեզ",
        "ով ա մարզել քեզ",
        "ով է մոդելը պարապել",
        "ով ա մոդելը պարապել",
        # Russian
        "кто тебя создал",
        "кто создал тебя",
        "кто тебя обучил",
        "кто обучил модель",
        "кто твой создатель",
    ]
    if any(pat in text_lc for pat in creator_patterns):
        fixed_reply = "Կարեն Պողոսյան"
        await add_to_chat_history(message.from_user.id, "user", message.text)
        await add_to_chat_history(message.from_user.id, "model", fixed_reply)
        await send_safe_html(message, fixed_reply)
        return

    processing_msg = await message.answer("🤖...")
    response_text = await gemini_service.chat_with_ai(
        message.from_user.id, message.text, persona=persona
    )
    await processing_msg.delete()
    await send_safe_html(message, response_text)


@chat_router.message(F.voice, AppStates.in_chat)
@chat_router.message(F.voice, AppStates.in_roleplay)
async def process_voice_message(message: Message, state: FSMContext, bot: Bot, user_db: dict):
    i18n = getattr(bot, "i18n", {})
    fsm_data = await state.get_data()
    persona = fsm_data.get("persona")

    processing_msg = await message.answer("🎤...")

    try:
        # Ներբեռնում ենք ձայնային հաղորդագրությունը
        voice = message.voice
        file_info = await bot.get_file(voice.file_id)
        
        # Օգտագործում ենք BytesIO հիշողության մեջ պահելու համար
        import io
        voice_buffer = io.BytesIO()
        await bot.download_file(file_info.file_path, voice_buffer)
        voice_data = voice_buffer.getvalue()

        # Տրանսկրիպցիա (ձայնը տեքստի)
        transcribed_text = await gemini_service.transcribe_audio(voice_data)
        
        if not transcribed_text:
            await processing_msg.edit_text(_("could_not_understand_audio", i18n))
            return

        # Ուղարկում ենք Gemini-ին
        response_text = await gemini_service.chat_with_ai(
            message.from_user.id, transcribed_text, persona=persona
        )

        await processing_msg.delete()
        
        # Ուղարկում ենք տեքստային պատասխանը
        await send_safe_html(message, f"<b>You:</b> <i>{transcribed_text}</i>\n\n{response_text}")

        # Պատրաստում ենք ձայնային պատասխանը (TTS)
        # Օգտագործում ենք օգտատիրոջ սովորած լեզուն կամ interface լեզուն
        learning_lang = user_db.get("learning_lang", "en")
        
        voice_file = await text_to_speech_file(response_text, lang=learning_lang)
        if voice_file:
            await message.answer_voice(voice_file)

    except Exception as e:
        import logging
        logging.error(f"Voice processing error: {e}")
        await processing_msg.edit_text(_("voice_error", i18n))


@chat_router.message(
    F.state.in_([AppStates.in_chat, AppStates.in_roleplay]), Command("reset")
)
async def cmd_reset_chat(message: Message, bot: Bot):
    i18n = getattr(bot, "i18n", {})
    await clear_chat_history(message.from_user.id)
    await message.answer(_("chat_history_cleared", i18n))
