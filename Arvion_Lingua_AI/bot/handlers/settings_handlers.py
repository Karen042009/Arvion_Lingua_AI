import html
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.middlewares.localization import _, Localization, get_all_translations
from bot.keyboards.reply import get_dynamic_reply_keyboard
from database.db_utils import update_user_setting, get_or_create_user
from config import (
    SUPPORTED_LANGUAGES, LEARNING_LEVELS,
    SUPPORTED_PROGRAMMING_LANGUAGES, PROGRAMMING_LEVELS
)
from bot.states.app_states import AppStates
from pathlib import Path

settings_router = Router()

def find_key_by_display_name(display_name: str, data_dict: dict) -> str | None:
    for key, value in data_dict.items():
        if isinstance(value, dict) and value.get('display_name') == display_name:
            return key
        if isinstance(value, str) and value == display_name:
            return key
    return None

async def show_settings_menu(message: Message, i18n: dict, user_db: dict, state: FSMContext):
    await state.set_state(AppStates.in_settings)
    mode = user_db.get('learning_mode', 'human')

    if mode == 'human':
        lang_name = SUPPORTED_LANGUAGES[user_db['learning_lang']]['display_name']
        level_name = LEARNING_LEVELS[user_db['learning_level']]
    else:
        lang_name = SUPPORTED_PROGRAMMING_LANGUAGES[user_db['programming_lang']]['display_name']
        level_name = PROGRAMMING_LEVELS[user_db['programming_level']]

    interface_lang_name = SUPPORTED_LANGUAGES[user_db['interface_lang']]['display_name']
    native_lang_name = SUPPORTED_LANGUAGES[user_db['native_lang']]['display_name']
    mode_text = i18n.get('mode_human' if mode == 'human' else 'mode_programming')

    text = _('settings_header', i18n) + "\n\n"
    text += f"🌐 {i18n.get('interface_lang_button')}: <b>{interface_lang_name}</b>\n"
    if mode == 'human':
        text += f"🗣️ {i18n.get('native_lang_button')}: <b>{native_lang_name}</b>\n"
    text += f"🔄 {i18n.get('learning_mode_button')}: <b>{mode_text}</b>\n"
    text += f"🎓 {i18n.get('learning_lang_button')}: <b>{lang_name}</b>\n"
    text += f"📊 {i18n.get('level_button')}: <b>{level_name}</b>"

    buttons = [
        i18n.get('interface_lang_button'),
        i18n.get('learning_mode_button'),
        i18n.get('learning_lang_button'),
        i18n.get('level_button'),
    ]
    if mode == 'human':
        buttons.insert(1, i18n.get('native_lang_button'))

    await message.answer(
        text,
        reply_markup=get_dynamic_reply_keyboard(buttons, i18n, 'back_to_main_menu')
    )

async def cb_main_menu_settings(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await show_settings_menu(message, i18n, user_db, state)

@settings_router.message(AppStates.in_settings)
async def process_settings_choice(message: Message, i18n: dict, user_db: dict, state: FSMContext, bot: Bot):
    locales = bot.loc_middleware.locales
    choice = message.text

    if choice in get_all_translations('interface_lang_button', locales):
        await state.set_state(AppStates.awaiting_interface_lang)
        lang_names = [v['display_name'] for v in SUPPORTED_LANGUAGES.values()]
        await message.answer(
            _('select_interface_lang', i18n),
            reply_markup=get_dynamic_reply_keyboard(lang_names, i18n, 'back_to_settings_menu')
        )
    elif choice in get_all_translations('native_lang_button', locales) and user_db.get('learning_mode') == 'human':
        await state.set_state(AppStates.awaiting_native_lang)
        lang_names = [v['display_name'] for v in SUPPORTED_LANGUAGES.values()]
        await message.answer(
            _('select_native_lang', i18n),
            reply_markup=get_dynamic_reply_keyboard(lang_names, i18n, 'back_to_settings_menu')
        )
    elif choice in get_all_translations('learning_mode_button', locales):
        await state.set_state(AppStates.awaiting_learning_mode)
        modes = [i18n.get('mode_human'), i18n.get('mode_programming')]
        await message.answer(
            _('select_learning_mode', i18n),
            reply_markup=get_dynamic_reply_keyboard(modes, i18n, 'back_to_settings_menu')
        )
    elif choice in get_all_translations('learning_lang_button', locales):
        await state.set_state(AppStates.awaiting_learning_subject)
        if user_db.get('learning_mode') == 'human':
            subjects = [v['display_name'] for v in SUPPORTED_LANGUAGES.values()]
            prompt = _('select_learning_lang', i18n)
        else:
            subjects = [v['display_name'] for v in SUPPORTED_PROGRAMMING_LANGUAGES.values()]
            prompt = _('select_programming_lang', i18n)
        await message.answer(prompt, reply_markup=get_dynamic_reply_keyboard(subjects, i18n, 'back_to_settings_menu'))

    elif choice in get_all_translations('level_button', locales):
        await state.set_state(AppStates.awaiting_level)
        if user_db.get('learning_mode') == 'human':
            levels = list(LEARNING_LEVELS.values())
            prompt = _('select_learning_level', i18n)
        else:
            levels = list(PROGRAMMING_LEVELS.values())
            prompt = _('select_programming_level', i18n)
        await message.answer(prompt, reply_markup=get_dynamic_reply_keyboard(levels, i18n, 'back_to_settings_menu'))
    else:
        await message.answer(_('unknown_command', i18n))

async def process_back_to_settings(message: Message, i18n: dict, user_db: dict, state: FSMContext):
    await show_settings_menu(message, i18n, user_db, state)

@settings_router.message(F.text.in_([
    "⬅️ Back to Settings", "⬅️ Назад в настройки", "⬅️ Հետ՝ կարգավորումներ", "⬅️ Volver a Ajustes",
    "⬅️ Retour aux Paramètres", "⬅️ Zurück zu den Einstellungen", "⬅️ Torna alle Impostazioni", "⬅️ 返回设置",
    "⬅️ 設定に戻る", "⬅️ 설정으로 돌아가기", "⬅️ सेटिंग्स पर वापस", "⬅️ Voltar para Configurações", "⬅️ العودة إلى الإعدادات"
]))
async def handle_back_to_settings_menu(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await process_back_to_settings(message, i18n, user_db, state)

async def update_and_show_menu(message: Message, setting_name: str, setting_value: str, state: FSMContext, bot: Bot):
    await update_user_setting(message.from_user.id, setting_name, setting_value)
    user_db = await get_or_create_user(message.from_user.id)
    i18n = bot.i18n
    if setting_name == 'interface_lang':
        locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
        loc_middleware = Localization(locales_dir)
        i18n = loc_middleware.locales.get(setting_value, loc_middleware.default_lang_texts)
        bot.i18n = i18n
    await message.answer(_('settings_updated', i18n), show_alert=False)
    await show_settings_menu(message, i18n, user_db, state)

@settings_router.message(AppStates.awaiting_interface_lang)
async def process_interface_lang(message: Message, state: FSMContext, bot: Bot):
    lang_code = find_key_by_display_name(message.text, SUPPORTED_LANGUAGES)
    if lang_code:
        await update_and_show_menu(message, 'interface_lang', lang_code, state, bot)

@settings_router.message(AppStates.awaiting_native_lang)
async def process_native_lang(message: Message, state: FSMContext, bot: Bot):
    lang_code = find_key_by_display_name(message.text, SUPPORTED_LANGUAGES)
    if lang_code:
        await update_and_show_menu(message, 'native_lang', lang_code, state, bot)

@settings_router.message(AppStates.awaiting_learning_mode)
async def process_learning_mode(message: Message, state: FSMContext, bot: Bot, i18n: dict):
    if message.text == i18n.get('mode_human'):
        await update_and_show_menu(message, 'learning_mode', 'human', state, bot)
    elif message.text == i18n.get('mode_programming'):
        await update_and_show_menu(message, 'learning_mode', 'programming', state, bot)

@settings_router.message(AppStates.awaiting_learning_subject)
async def process_learning_subject(message: Message, state: FSMContext, bot: Bot, user_db: dict):
    if user_db.get('learning_mode') == 'human':
        code = find_key_by_display_name(message.text, SUPPORTED_LANGUAGES)
        if code: await update_and_show_menu(message, 'learning_lang', code, state, bot)
    else:
        code = find_key_by_display_name(message.text, SUPPORTED_PROGRAMMING_LANGUAGES)
        if code: await update_and_show_menu(message, 'programming_lang', code, state, bot)

@settings_router.message(AppStates.awaiting_level)
async def process_level(message: Message, state: FSMContext, bot: Bot, user_db: dict):
    if user_db.get('learning_mode') == 'human':
        code = find_key_by_display_name(message.text, LEARNING_LEVELS)
        if code: await update_and_show_menu(message, 'learning_level', code, state, bot)
    else:
        code = find_key_by_display_name(message.text, PROGRAMMING_LEVELS)
        if code: await update_and_show_menu(message, 'programming_level', code, state, bot)