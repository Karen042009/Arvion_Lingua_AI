from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from config import (
    SUPPORTED_LANGUAGES, LEARNING_LEVELS,
    SUPPORTED_PROGRAMMING_LANGUAGES, PROGRAMMING_LEVELS
)

def get_settings_keyboard(i18n: dict, user_db: dict) -> InlineKeyboardMarkup:
    mode = user_db.get('learning_mode', 'human')

    if mode == 'human':
        lang_code = user_db.get('learning_lang', 'es')
        lang_name = SUPPORTED_LANGUAGES.get(lang_code, {}).get('display_name')
        level_code = user_db.get('learning_level', 'beginner')
        level_name = LEARNING_LEVELS.get(level_code)
    else:
        lang_code = user_db.get('programming_lang', 'python')
        lang_name = SUPPORTED_PROGRAMMING_LANGUAGES.get(
            lang_code, {}
        ).get('display_name')
        level_code = user_db.get('programming_level', 'beginner')
        level_name = PROGRAMMING_LEVELS.get(level_code)

    interface_lang_name = SUPPORTED_LANGUAGES.get(
        user_db.get('interface_lang', 'en'), {}
    ).get('display_name')
    native_lang_name = SUPPORTED_LANGUAGES.get(
        user_db.get('native_lang', 'en'), {}
    ).get('display_name')
    mode_text = i18n.get(
        'mode_human' if mode == 'human' else 'mode_programming'
    )

    buttons = [
        [
            InlineKeyboardButton(
                text=f"🌐 {i18n.get('interface_lang_button')}: {interface_lang_name}",
                callback_data="settings:interface_lang"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔄 {i18n.get('learning_mode_button')}: {mode_text}",
                callback_data="settings:learning_mode"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🎓 {i18n.get('learning_lang_button')}: {lang_name}",
                callback_data="settings:learning_subject"
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📊 {i18n.get('level_button')}: {level_name}",
                callback_data="settings:level"
            )
        ],
    ]
    if mode == 'human':
        buttons.insert(2, [
            InlineKeyboardButton(
                text=f"🗣️ {i18n.get('native_lang_button')}: {native_lang_name}",
                callback_data="settings:native_lang"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text=i18n.get('back_to_main_menu'),
            callback_data="back_to_main_menu"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_language_choice_keyboard(
    callback_prefix: str, lang_dict: dict, back_callback: str
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=names['display_name'],
                callback_data=f"{callback_prefix}:{code}"
            )
        ]
        for code, names in lang_dict.items()
    ]
    buttons.append([
        InlineKeyboardButton(text='⬅️ Back', callback_data=back_callback)
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_level_choice_keyboard(
    callback_prefix: str, level_dict: dict, back_callback: str
) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=name, callback_data=f"{callback_prefix}:{code}"
            )
        ]
        for code, name in level_dict.items()
    ]
    buttons.append([
        InlineKeyboardButton(text='⬅️ Back', callback_data=back_callback)
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_learning_mode_keyboard(i18n: dict) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=i18n.get('mode_human'),
                callback_data="set_learning_mode:human"
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('mode_programming'),
                callback_data="set_learning_mode:programming"
            )
        ],
        [
            InlineKeyboardButton(
                text='⬅️ Back', callback_data="set_learning_mode:back"
            )
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_learning_menu_keyboard(
    i18n: dict, mode: str
) -> InlineKeyboardMarkup:
    if mode == 'human':
        buttons = [
            [
                InlineKeyboardButton(
                    text=i18n.get('new_word', '📝 New Word'),
                    callback_data="learn:word"
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get('quiz', '🧩 Quiz'),
                    callback_data="learn:quiz"
                )
            ]
        ]
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    text=i18n.get('new_concept', '💡 New Concept'),
                    callback_data="learn:concept"
                )
            ],
            [
                InlineKeyboardButton(
                    text=i18n.get('quiz', '🧩 Quiz'),
                    callback_data="learn:quiz"
                )
            ]
        ]
    buttons.append([
        InlineKeyboardButton(
            text=i18n.get('back_to_main_menu'),
            callback_data="back_to_main_menu"
        )
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_quiz_keyboard(options: list) -> tuple[InlineKeyboardMarkup, bool]:
    use_labels = any(len(opt) > 25 for opt in options)

    if use_labels:
        labels = ["A", "B", "C", "D"]
        buttons = [
            [InlineKeyboardButton(
                text=label, callback_data=f"quiz_answer:{i}"
            )]
            for i, label in enumerate(labels)
        ]
    else:
        buttons = [
            [InlineKeyboardButton(
                text=option, callback_data=f"quiz_answer:{i}"
            )]
            for i, option in enumerate(options)
        ]

    return InlineKeyboardMarkup(inline_keyboard=buttons), use_labels


def get_translation_actions_keyboard(i18n: dict) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=i18n.get('tts_source'), callback_data="tts:source"
        ),
        InlineKeyboardButton(
            text=i18n.get('tts_target'), callback_data="tts:target"
        ),
    ]])


def get_universal_translator_keyboard(
    i18n: dict,
    source_lang_code: str,
    target_lang_code: str,
    show_lang_list: str | None = None
) -> InlineKeyboardMarkup:
    source_lang_name = SUPPORTED_LANGUAGES.get(
        source_lang_code, {}
    ).get('display_name', i18n.get('auto_detect', 'Auto-detect'))
    target_lang_name = SUPPORTED_LANGUAGES.get(
        target_lang_code, {}
    ).get('display_name', 'English')

    top_row = [
        InlineKeyboardButton(
            text=source_lang_name, callback_data="translator:change_source"
        ),
        InlineKeyboardButton(
            text="🔄", callback_data="translator:swap"
        ),
        InlineKeyboardButton(
            text=target_lang_name, callback_data="translator:change_target"
        )
    ]

    keyboard = [top_row]

    if show_lang_list:
        lang_list_buttons = []
        row = []
        callback_prefix = f"translator:set_{show_lang_list}"

        if show_lang_list == 'source':
            row.append(InlineKeyboardButton(
                text=i18n.get('auto_detect', 'Auto-detect'),
                callback_data=f"{callback_prefix}:auto"
            ))

        for code, names in SUPPORTED_LANGUAGES.items():
            row.append(InlineKeyboardButton(
                text=names['display_name'],
                callback_data=f"{callback_prefix}:{code}"
            ))
            if len(row) >= 3:
                lang_list_buttons.append(row)
                row = []
        if row:
            lang_list_buttons.append(row)

        keyboard.extend(lang_list_buttons)

    keyboard.append([
        InlineKeyboardButton(
            text=i18n.get('back_to_main_menu'),
            callback_data="back_to_main_menu"
        )
    ])

    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_post_quiz_keyboard(i18n: dict) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=i18n.get('next_quiz'), callback_data="learn:quiz"
            ),
            InlineKeyboardButton(
                text=i18n.get('back_to_learn_menu'),
                callback_data="back_to_learn_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_chat_mode_keyboard(i18n: dict) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=i18n.get('chat_mode_regular'),
                callback_data="chat_mode:regular"
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('chat_mode_roleplay'),
                callback_data="chat_mode:roleplay"
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('back_to_main_menu'),
                callback_data="back_to_main_menu"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def get_roleplay_scenarios_keyboard(i18n: dict) -> InlineKeyboardMarkup:
    buttons = [
        [
            InlineKeyboardButton(
                text=i18n.get('roleplay_cafe'),
                callback_data="roleplay_scenario:cafe"
            ),
            InlineKeyboardButton(
                text=i18n.get('roleplay_hotel'),
                callback_data="roleplay_scenario:hotel"
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('roleplay_job_interview'),
                callback_data="roleplay_scenario:job_interview"
            )
        ],
        [
            InlineKeyboardButton(
                text=i18n.get('back_to_chat_modes'),
                callback_data="main_menu:chat"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)