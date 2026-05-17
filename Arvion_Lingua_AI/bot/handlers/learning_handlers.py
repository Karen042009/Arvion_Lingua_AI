import html
import asyncio
from pathlib import Path
from aiogram import Router, F, Bot
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from bot.middlewares.localization import _, get_all_translations, Localization
from bot.states.app_states import AppStates
from bot.services.gemini_service import GeminiService
from bot.keyboards.reply import get_dynamic_reply_keyboard
from database.db_utils import get_or_create_user, increment_user_stat
from bot.utils.message_utils import send_safe_html
from config import (
    SUPPORTED_LANGUAGES, LEARNING_LEVELS,
    SUPPORTED_PROGRAMMING_LANGUAGES, PROGRAMMING_LEVELS
)

# --- ՍԿԻԶԲ։ Կոճակների ֆիլտրերի ուղղում ---
locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
loc_middleware = Localization(locales_dir)
all_locales = loc_middleware.locales
# --- ԱՎԱՐՏ։ Կոճակների ֆիլտրերի ուղղում ---

learning_router = Router()
gemini_service = GeminiService()

async def show_learning_menu(message: Message, i18n: dict, user_db: dict, state: FSMContext):
    await state.set_state(AppStates.in_learning_menu)
    mode = user_db.get('learning_mode', 'human')
    text, buttons = "", []

    if mode == 'human':
        lang_name = SUPPORTED_LANGUAGES[user_db['learning_lang']]['display_name']
        level = LEARNING_LEVELS[user_db['learning_level']]
        text = _('learn_menu_text_human', i18n, learning_lang=lang_name, level=level)
        buttons = [i18n.get('new_word'), i18n.get('quiz')]
    else:
        lang_name = SUPPORTED_PROGRAMMING_LANGUAGES[user_db['programming_lang']]['display_name']
        level = PROGRAMMING_LEVELS[user_db['programming_level']]
        text = _('learn_menu_text_programming', i18n, programming_lang=lang_name, level=level)
        buttons = [i18n.get('new_concept'), i18n.get('quiz')]

    await message.answer(text, reply_markup=get_dynamic_reply_keyboard(buttons, i18n, 'back_to_main_menu'))

async def cb_main_menu_learn(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await state.clear()
    await state.update_data(recent_items=[])
    await show_learning_menu(message, i18n, user_db, state)

def is_quiz_valid(data: dict | None) -> bool:
    if not data: return False
    keys = ["question", "options", "correct_answer_text"]
    return all(k in data for k in keys) and len(data["options"]) >= 2

def is_word_valid(data: dict | None) -> bool:
    if not data: return False
    return all(k in data for k in ["item", "translation"])

def is_concept_valid(data: dict | None) -> bool:
    if not data: return False
    return all(k in data for k in ["item", "explanation"])

async def handle_learn_activity_request(message: Message, user_db: dict, state: FSMContext, bot: Bot, activity_type: str):
    i18n = getattr(bot, 'i18n', {})
    mode = user_db.get('learning_mode', 'human')

    generating_text_key = f"generating_{activity_type}"
    processing_msg = await message.answer(_(generating_text_key, i18n))

    item_data, validation_func = None, None
    if activity_type == 'quiz': validation_func = is_quiz_valid
    elif mode == 'human' and activity_type == 'word': validation_func = is_word_valid
    elif mode == 'programming' and activity_type == 'concept': validation_func = is_concept_valid

    for _i in range(3):
        fsm_data = await state.get_data()
        recent_items = fsm_data.get("recent_items", [])
        lang_info, level = {}, ""

        if mode == 'human':
            lang_info['native'] = SUPPORTED_LANGUAGES[user_db['native_lang']]['gemini_name']
            lang_info['learning'] = SUPPORTED_LANGUAGES[user_db['learning_lang']]['gemini_name']
            level = LEARNING_LEVELS[user_db['learning_level']]
        else:
            lang_info['programming'] = SUPPORTED_PROGRAMMING_LANGUAGES[user_db['programming_lang']]['display_name']
            level = PROGRAMMING_LEVELS[user_db['programming_level']]
            lang_info['interface_lang_name'] = SUPPORTED_LANGUAGES[user_db['interface_lang']]['gemini_name']

        api_response = await gemini_service.get_learning_item(activity_type, mode, lang_info, level, recent_items)

        if validation_func and validation_func(api_response):
            item_data = api_response
            break
        await asyncio.sleep(0.5)

    await processing_msg.delete()

    if not item_data:
        await message.answer(_('generation_error', i18n))
        await show_learning_menu(message, i18n, user_db, state)
        return

    current_state_data = await state.get_data()
    new_recent_items = current_state_data.get("recent_items", [])
    new_item = item_data.get("item") or item_data.get("question")
    if new_item: new_recent_items.append(new_item)
    data_to_update = {"recent_items": new_recent_items[-15:]}

    if activity_type == 'quiz':
        await state.set_state(AppStates.awaiting_quiz_answer)
        question = html.escape(item_data.get("question", ""))
        options = [html.escape(opt) for opt in item_data.get("options", [])]
        correct_answer_text = html.escape(item_data.get("correct_answer_text", ""))

        data_to_update["correct_quiz_answer"] = correct_answer_text
        question_text = _('quiz_question', i18n, question=question)
        
        use_labels = any(len(opt) > 25 for opt in options)
        data_to_update['use_labels'] = use_labels
        data_to_update['quiz_options'] = options

        if use_labels:
            labeled_options = "\n".join(f"<b>{chr(65+i)}:</b> {opt}" for i, opt in enumerate(options))
            question_text += "\n\n" + labeled_options
            reply_buttons = [chr(65+i) for i in range(len(options))]
        else:
            reply_buttons = options

        await state.update_data(**data_to_update)
        await message.answer(question_text, reply_markup=get_dynamic_reply_keyboard(reply_buttons, i18n, 'back_to_learn_menu'))

    elif mode == 'human' and activity_type == 'word':
        await state.set_state(AppStates.awaiting_learning_answer)
        data_to_update["original_text"] = item_data.get("item")
        data_to_update["source_lang"] = lang_info['learning']
        data_to_update["target_lang"] = lang_info['native']
        await state.update_data(**data_to_update)
        await message.answer(
            _('learn_word_prompt', i18n, level=level, text_to_translate=html.escape(item_data.get("item", ""))) +
            "\n\n" + _('learn_translate_this', i18n, target_lang_name=SUPPORTED_LANGUAGES[user_db['native_lang']]['display_name']),
            reply_markup=get_dynamic_reply_keyboard([], i18n, 'back_to_learn_menu')
        )

    elif mode == 'programming' and activity_type == 'concept':
        title = html.escape(item_data.get("item", ""))
        explanation = html.escape(item_data.get("explanation", ""))
        code = html.escape(item_data.get("code_example", ""))
        text = _('prog_concept_text', i18n, title=title, explanation=explanation, code=code)
        await send_safe_html(message, text, reply_markup=get_dynamic_reply_keyboard([i18n.get('next_concept')], i18n, 'back_to_learn_menu'))
        await increment_user_stat(message.from_user.id, 'words_learned_count')
        await state.update_data(**data_to_update)
        # Set state to in_learning_menu to allow "Next Concept" and "Back" buttons to be processed
        await state.set_state(AppStates.in_learning_menu)


@learning_router.message(
    AppStates.in_learning_menu,
    F.text.in_(
        get_all_translations("new_word", all_locales) +
        get_all_translations("new_concept", all_locales) +
        get_all_translations("quiz", all_locales)
    )
)
async def process_learn_menu_choice(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    mode = user_db.get('learning_mode', 'human')
    activity_map = {
        'word': get_all_translations('new_word', all_locales),
        'concept': get_all_translations('new_concept', all_locales),
        'quiz': get_all_translations('quiz', all_locales)
    }

    activity_type = None
    if message.text in activity_map['quiz']:
        activity_type = 'quiz'
    elif mode == 'human' and message.text in activity_map['word']:
        activity_type = 'word'
    elif mode == 'programming' and message.text in activity_map['concept']:
        activity_type = 'concept'

    if activity_type:
        await handle_learn_activity_request(message, user_db, state, bot, activity_type)


@learning_router.message(F.text.in_(get_all_translations("back_to_learn_menu", all_locales)))
async def handle_back_to_learn_menu(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await show_learning_menu(message, i18n, user_db, state)

@learning_router.message(AppStates.awaiting_learning_answer, F.text)
async def process_learning_answer(message: Message, state: FSMContext, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    user_answer = message.text
    data = await state.get_data()

    await increment_user_stat(message.from_user.id, 'words_learned_count')
    processing_msg = await message.answer(_('evaluating_answer', i18n))

    feedback = await gemini_service.evaluate_user_answer(
        original_text=data.get('original_text'),
        user_translation=user_answer,
        source_lang=data.get('source_lang'),
        target_lang=data.get('target_lang')
    )

    await processing_msg.delete()
    if feedback:
        await send_safe_html(message, _('ai_feedback', i18n, feedback=feedback))

    await show_learning_menu(message, i18n, user_db, state)

@learning_router.message(AppStates.awaiting_quiz_answer, F.text)
async def process_quiz_answer(message: Message, state: FSMContext, user_db: dict, bot: Bot):
    i18n = getattr(message.bot, 'i18n', {})
    data = await state.get_data()
    correct_answer_full_text = data.get('correct_quiz_answer')

    if correct_answer_full_text is None:
        await message.answer("Sorry, an error occurred.")
        await show_learning_menu(message, i18n, user_db, state)
        return

    user_choice_text = message.text
    if data.get('use_labels', False) and user_choice_text in ['A', 'B', 'C', 'D']:
        idx = ord(user_choice_text) - ord('A')
        options = data.get('quiz_options', [])
        if 0 <= idx < len(options):
            user_choice_text = options[idx]
    
    is_correct = correct_answer_full_text.strip().lower() == user_choice_text.strip().lower()

    if is_correct:
        await increment_user_stat(message.from_user.id, 'quizzes_passed_count')
        result_text = _('quiz_result_correct', i18n, answer=html.escape(user_choice_text))
    else:
        result_text = _('quiz_result_incorrect', i18n,
                        user_answer=html.escape(user_choice_text),
                        correct_answer=html.escape(correct_answer_full_text))

    await message.answer(
        result_text,
        reply_markup=get_dynamic_reply_keyboard([i18n.get('next_quiz')], i18n, 'back_to_learn_menu')
    )
    await state.set_state(AppStates.in_learning_menu)

@learning_router.message(
    AppStates.in_learning_menu,
    F.text.in_(
        get_all_translations("next_quiz", all_locales) +
        get_all_translations("next_concept", all_locales)
    )
)
async def handle_next_activity(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    activity_type = 'concept' if message.text in get_all_translations("next_concept", all_locales) else 'quiz'
    await handle_learn_activity_request(message, user_db, state, bot, activity_type)