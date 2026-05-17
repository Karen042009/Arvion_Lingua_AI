import io
import logging
import html
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, PhotoSize, ReplyKeyboardMarkup, KeyboardButton
from bot.middlewares.localization import _, get_all_translations, Localization
from bot.states.app_states import AppStates
from bot.services.gemini_service import GeminiService
from bot.services.tts_service import text_to_speech_file
from bot.keyboards.reply import (
    get_universal_translator_keyboard,
    get_dynamic_reply_keyboard,
    get_translation_actions_reply_keyboard,
)
from database.db_utils import increment_user_stat
from config import SUPPORTED_LANGUAGES

# --- ՍԿԻԶԲ։ Կոճակների ֆիլտրերի ուղղում ---
# Ստեղծում ենք Localization-ի օրինակ՝ բոլոր թարգմանությունները բեռնելու համար
locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
loc_middleware = Localization(locales_dir)
all_locales = loc_middleware.locales
# --- ԱՎԱՐՏ։ Կոճակների ֆիլտրերի ուղղում ---

translate_router = Router()
gemini_service = GeminiService()


def find_lang_key_by_name(lang_name: str, lang_dict: dict) -> str | None:
    for code, data in lang_dict.items():
        if data["display_name"] == lang_name:
            return code
    return None


async def show_translator_interface(message: Message, i18n: dict, state: FSMContext):
    await state.set_state(AppStates.in_translation_mode)
    data = await state.get_data()
    source_lang_code = data.get("source_lang", "auto")
    target_lang_code = data.get("target_lang", "en")

    source_lang_name = i18n.get("auto_detect")
    if source_lang_code != "auto":
        source_lang_name = SUPPORTED_LANGUAGES.get(source_lang_code, {}).get(
            "display_name", i18n.get("auto_detect")
        )

    target_lang_name = SUPPORTED_LANGUAGES.get(target_lang_code, {}).get("display_name")

    text = _("universal_translator_prompt", i18n) + "\n\n"
    text += f"<i>{i18n.get('source_lang_label')}:</i> <b>{source_lang_name}</b>\n"
    text += f"<i>{i18n.get('target_lang_label')}:</i> <b>{target_lang_name}</b>"

    # Build translator controls + Back to Menu button in one keyboard
    translator_buttons = [
        [
            KeyboardButton(text=i18n.get("translator_change_source")),
            KeyboardButton(text=i18n.get("translator_swap")),
            KeyboardButton(text=i18n.get("translator_change_target")),
        ],
        [KeyboardButton(text=i18n.get("back_to_main_menu"))],
    ]
    reply_kb = ReplyKeyboardMarkup(keyboard=translator_buttons, resize_keyboard=True)
    await message.answer(text, reply_markup=reply_kb)


async def cb_enter_translator(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, "i18n", {})
    await state.clear()
    await state.update_data(
        source_lang="auto", target_lang=user_db.get("native_lang", "en")
    )
    await show_translator_interface(message, i18n, state)


@translate_router.message(
    AppStates.in_translation_mode,
    F.text.in_(get_all_translations("translator_change_source", all_locales)),
)
async def handle_change_source_lang(message: Message, i18n: dict, state: FSMContext):
    await state.set_state(AppStates.awaiting_source_lang)
    lang_names = [i18n.get("auto_detect")] + [
        v["display_name"] for v in SUPPORTED_LANGUAGES.values()
    ]
    await message.answer(
        _("select_source_lang", i18n),
        reply_markup=get_dynamic_reply_keyboard(lang_names, i18n, "back_to_translator"),
    )


@translate_router.message(
    AppStates.in_translation_mode,
    F.text.in_(get_all_translations("translator_change_target", all_locales)),
)
async def handle_change_target_lang(message: Message, i18n: dict, state: FSMContext):
    await state.set_state(AppStates.awaiting_target_lang)
    lang_names = [v["display_name"] for v in SUPPORTED_LANGUAGES.values()]
    await message.answer(
        _("select_target_lang", i18n),
        reply_markup=get_dynamic_reply_keyboard(lang_names, i18n, "back_to_translator"),
    )


@translate_router.message(
    AppStates.in_translation_mode,
    F.text.in_(get_all_translations("translator_swap", all_locales)),
)
async def handle_swap_langs(message: Message, i18n: dict, state: FSMContext):
    data = await state.get_data()
    source_lang, target_lang = data.get("source_lang", "auto"), data.get(
        "target_lang", "en"
    )
    if source_lang == "auto":
        await message.answer(_("cannot_swap_auto", i18n))
        return
    await state.update_data(source_lang=target_lang, target_lang=source_lang)
    await show_translator_interface(message, i18n, state)


@translate_router.message(
    F.text.in_(get_all_translations("back_to_translator", all_locales))
)
async def handle_back_to_translator(message: Message, i18n: dict, state: FSMContext):
    await show_translator_interface(message, i18n, state)


@translate_router.message(AppStates.awaiting_source_lang)
async def process_set_source_lang(message: Message, i18n: dict, state: FSMContext):
    lang_code = (
        "auto"
        if message.text == i18n.get("auto_detect")
        else find_lang_key_by_name(message.text, SUPPORTED_LANGUAGES)
    )

    if lang_code:
        await state.update_data(source_lang=lang_code)
        await show_translator_interface(message, i18n, state)


@translate_router.message(AppStates.awaiting_target_lang)
async def process_set_target_lang(message: Message, i18n: dict, state: FSMContext):
    lang_code = find_lang_key_by_name(message.text, SUPPORTED_LANGUAGES)
    if lang_code:
        await state.update_data(target_lang=lang_code)
        await show_translator_interface(message, i18n, state)


async def perform_translation(
    message: Message,
    i18n: dict,
    state: FSMContext,
    text_to_translate: str | None = None,
    image_bytes: io.BytesIO | None = None,
):
    processing_msg = await message.answer(_("translating", i18n))
    data = await state.get_data()
    source_lang_code = data.get("source_lang", "auto")
    target_lang_code = data.get("target_lang", "en")

    target_lang_name = SUPPORTED_LANGUAGES[target_lang_code]["gemini_name"]
    source_lang_name = (
        "auto"
        if source_lang_code == "auto"
        else SUPPORTED_LANGUAGES[source_lang_code]["gemini_name"]
    )

    result = None
    if text_to_translate:
        result = await gemini_service.translate_text(
            text_to_translate, target_lang_name, source_lang_name
        )
    elif image_bytes:
        result = await gemini_service.get_text_from_image(image_bytes, target_lang_name)

    await processing_msg.delete()

    if result and result.get("translated_text"):
        await increment_user_stat(message.from_user.id, "translations_count")
        original_text = text_to_translate or result.get("found_text", "")
        translated_text = result.get("translated_text")

        detected_source_name = result.get("detected_language_name", source_lang_name)
        detected_code = next(
            (
                code
                for code, names in SUPPORTED_LANGUAGES.items()
                if names["gemini_name"].lower() == detected_source_name.lower()
            ),
            source_lang_code if source_lang_code != "auto" else "en",
        )
        await state.update_data(
            last_source_text=original_text,
            last_translated_text=translated_text,
            last_source_code=detected_code,
            last_target_code=target_lang_code,
        )
        await state.set_state(AppStates.awaiting_tts_choice)

        response_text = _(
            "translation_result",
            i18n,
            source_lang=html.escape(detected_source_name),
            target_lang=html.escape(target_lang_name),
            translated_text=html.escape(translated_text),
        )
        actions_buttons = [
            [
                KeyboardButton(text=i18n.get("tts_source")),
                KeyboardButton(text=i18n.get("tts_target")),
            ],
            [
                KeyboardButton(text=i18n.get("back_to_translator")),
                KeyboardButton(text=i18n.get("back_to_main_menu")),
            ],
        ]
        actions_kb = ReplyKeyboardMarkup(
            keyboard=actions_buttons, resize_keyboard=True, one_time_keyboard=True
        )
        await message.answer(response_text, reply_markup=actions_kb)
    else:
        await message.answer(_("translation_error", i18n))


@translate_router.message(AppStates.in_translation_mode, F.text)
async def process_text_translation(message: Message, state: FSMContext, i18n: dict):
    await perform_translation(message, i18n, state, text_to_translate=message.text)


@translate_router.message(AppStates.in_translation_mode, F.photo)
async def process_image_translation(
    message: Message, state: FSMContext, bot: Bot, i18n: dict
):
    photo: PhotoSize = message.photo[-1]
    image_bytes = io.BytesIO()
    await bot.download(file=photo.file_id, destination=image_bytes)
    await perform_translation(message, i18n, state, image_bytes=image_bytes)


@translate_router.message(AppStates.awaiting_tts_choice)
async def process_tts_choice(message: Message, state: FSMContext, bot: Bot, i18n: dict):
    locales = bot.loc_middleware.locales
    choice = message.text
    action = None

    if choice in get_all_translations("tts_source", locales):
        action = "source"
    elif choice in get_all_translations("tts_target", locales):
        action = "target"
    elif choice in get_all_translations("back_to_translator", locales):
        await show_translator_interface(message, i18n, state)
        return
    else:
        await show_translator_interface(message, i18n, state)
        await process_text_translation(message, state, i18n)
        return

    if not action:
        return

    data = await state.get_data()
    text_map = {
        "source": data.get("last_source_text"),
        "target": data.get("last_translated_text"),
    }
    lang_code_map = {
        "source": data.get("last_source_code"),
        "target": data.get("last_target_code"),
    }
    text = text_map.get(action)
    lang_code = lang_code_map.get(action)

    if not text or not lang_code:
        await message.answer("Error: Text or language not found for TTS.")
        return

    processing_tts_msg = await message.answer("▶️ Generating voice...")
    audio_file = await text_to_speech_file(text, lang_code)
    await processing_tts_msg.delete()

    if audio_file:
        await message.answer_voice(audio_file)
    else:
        await message.answer(f"Failed to generate voice for '{lang_code}'.")
