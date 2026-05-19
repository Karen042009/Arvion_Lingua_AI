from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# Default fallback texts in English
DEFAULT_TEXTS = {
    'translate_button': '🌐 Translate',
    'learn_button': '🎓 Learn',
    'chat_button': '🤖 Chat with AI',
    'settings_button': '⚙️ Settings',
    'games_button': '🎮 Games',
    'culture_button': '🌍 Culture & Grammar',
    'back_to_translator': '⬅️ Back to Translator'
}

def get_text(i18n: dict, key: str) -> str:
    return i18n.get(key, DEFAULT_TEXTS.get(key, f'_{key}_'))

def get_main_reply_keyboard(i18n: dict) -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text=get_text(i18n, 'translate_button')),
            KeyboardButton(text=get_text(i18n, 'learn_button'))
        ],
        [
            KeyboardButton(text=get_text(i18n, 'chat_button')),
            KeyboardButton(text=get_text(i18n, 'settings_button'))
        ],
        [
            KeyboardButton(text=get_text(i18n, 'games_button')),
            KeyboardButton(text=get_text(i18n, 'culture_button'))
        ],
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_dynamic_reply_keyboard(
    items: list[str],
    i18n: dict,
    back_button_text_key: str | None = None
) -> ReplyKeyboardMarkup:
    # Filter out any None items to prevent errors
    buttons = [
        [KeyboardButton(text=item)] for item in items if item is not None
    ]
    if back_button_text_key:
        back_text = get_text(i18n, back_button_text_key)
        if back_text:
            buttons.append([KeyboardButton(text=back_text)])

    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)

def get_universal_translator_keyboard(i18n: dict) -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text=get_text(i18n, 'translator_change_source')),
            KeyboardButton(text=get_text(i18n, 'translator_swap')),
            KeyboardButton(text=get_text(i18n, 'translator_change_target'))
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_translation_actions_reply_keyboard(i18n: dict) -> ReplyKeyboardMarkup:
    buttons = [
        [
            KeyboardButton(text=get_text(i18n, 'tts_source')),
            KeyboardButton(text=get_text(i18n, 'tts_target'))
        ],
        [
            KeyboardButton(text=get_text(i18n, 'back_to_translator'))
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True, one_time_keyboard=True)