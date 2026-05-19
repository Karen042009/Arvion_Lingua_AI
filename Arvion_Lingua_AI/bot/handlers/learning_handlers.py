import html
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
from database.db_utils import get_or_create_user, increment_user_stat, save_word
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
        buttons = [
            i18n.get('new_word'),
            i18n.get('quiz'),
            i18n.get('fill_blank_button'),
            i18n.get('story_mode_button'),
            i18n.get('idiom_button'),
            i18n.get('grammar_check_button'),
        ]
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
    if not data:
        return False
    keys = ["question", "options", "correct_answer_text"]
    if not all(k in data for k in keys):
        return False
    if len(data["options"]) < 2:
        return False
    # Verify correct_answer_text matches one of the options (case-insensitive)
    correct = data["correct_answer_text"].strip().lower()
    options_lower = [opt.strip().lower() for opt in data["options"]]
    if correct not in options_lower:
        # Try to auto-fix: find closest match
        for i, opt in enumerate(options_lower):
            if correct in opt or opt in correct:
                data["correct_answer_text"] = data["options"][i]
                return True
        logging.warning(f"Quiz correct_answer_text not in options: '{data['correct_answer_text']}' not in {data['options']}")
        return False
    return True

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
        data_to_update["word_translation"] = item_data.get("translation")
        data_to_update["source_lang"] = lang_info['learning']
        data_to_update["target_lang"] = lang_info['native']
        await state.update_data(**data_to_update)
        buttons = [i18n.get("save_word_button", "💾 Save Word")]
        await message.answer(
            _('learn_word_prompt', i18n, level=level, text_to_translate=html.escape(item_data.get("item", ""))) +
            "\n\n" + _('learn_translate_this', i18n, target_lang_name=SUPPORTED_LANGUAGES[user_db['native_lang']]['display_name']),
            reply_markup=get_dynamic_reply_keyboard(buttons, i18n, 'back_to_learn_menu')
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


# ─── Fill in the Blank ───────────────────────────────────────────────────────

@learning_router.message(
    AppStates.in_learning_menu,
    F.text.in_(get_all_translations("fill_blank_button", all_locales))
)
async def handle_fill_blank(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    i18n = getattr(bot, 'i18n', {})
    if user_db.get('learning_mode') != 'human':
        await message.answer(_('human_mode_only', i18n))
        return

    processing_msg = await message.answer(_('generating_exercise', i18n))
    learning_lang = SUPPORTED_LANGUAGES[user_db['learning_lang']]['gemini_name']
    native_lang = SUPPORTED_LANGUAGES[user_db['native_lang']]['gemini_name']
    level = LEARNING_LEVELS[user_db['learning_level']]

    result = await gemini_service.generate_fill_in_blank(learning_lang, native_lang, level)
    await processing_msg.delete()

    if not result or not result.get('sentence'):
        await message.answer(_('generation_error', i18n))
        await show_learning_menu(message, i18n, user_db, state)
        return

    sentence = html.escape(result['sentence'])
    translation = html.escape(result.get('translation', ''))
    options = [html.escape(opt) for opt in result.get('options', [])]
    correct = html.escape(result.get('correct_answer_text', ''))
    explanation = html.escape(result.get('explanation', ''))

    await state.set_state(AppStates.awaiting_fill_blank_answer)
    await state.update_data(
        fill_correct=correct,
        fill_explanation=explanation,
        fill_options=options,
    )

    use_labels = any(len(opt) > 20 for opt in options)
    question_text = (
        f"✏️ <b>{_('fill_blank_title', i18n)}</b>\n\n"
        f"<code>{sentence}</code>\n\n"
        f"<i>{translation}</i>"
    )

    if use_labels:
        labeled = "\n".join(f"<b>{chr(65+i)}:</b> {opt}" for i, opt in enumerate(options))
        question_text += f"\n\n{labeled}"
        reply_buttons = [chr(65+i) for i in range(len(options))]
    else:
        reply_buttons = options

    await message.answer(
        question_text,
        reply_markup=get_dynamic_reply_keyboard(reply_buttons, i18n, 'back_to_learn_menu')
    )


@learning_router.message(AppStates.awaiting_fill_blank_answer, F.text)
async def process_fill_blank_answer(message: Message, state: FSMContext, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    data = await state.get_data()
    correct = data.get('fill_correct', '')
    explanation = data.get('fill_explanation', '')
    options = data.get('fill_options', [])

    user_answer = message.text
    # Handle label answers (A, B, C, D)
    if user_answer in ['A', 'B', 'C', 'D'] and options:
        idx = ord(user_answer) - ord('A')
        if 0 <= idx < len(options):
            user_answer = options[idx]

    is_correct = user_answer.strip().lower() == correct.strip().lower()

    if is_correct:
        await increment_user_stat(message.from_user.id, 'quizzes_passed_count')
        text = (
            f"✅ <b>{_('correct', i18n)}</b>\n\n"
            f"💬 {explanation}"
        )
    else:
        text = (
            f"❌ <b>{_('incorrect', i18n)}</b>\n"
            f"✅ {_('correct_answer_was', i18n)}: <b>{correct}</b>\n\n"
            f"💬 {explanation}"
        )

    await message.answer(
        text,
        reply_markup=get_dynamic_reply_keyboard(
            [i18n.get('fill_blank_button', '✏️ Fill in the Blank')],
            i18n, 'back_to_learn_menu'
        )
    )
    await state.set_state(AppStates.in_learning_menu)


# ─── Story Mode ──────────────────────────────────────────────────────────────

STORY_TOPICS = ['travel', 'food', 'friendship', 'adventure', 'work', 'family', 'nature', 'technology']

@learning_router.message(
    AppStates.in_learning_menu,
    F.text.in_(get_all_translations("story_mode_button", all_locales))
)
async def handle_story_mode(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    i18n = getattr(bot, 'i18n', {})
    if user_db.get('learning_mode') != 'human':
        await message.answer(_('human_mode_only', i18n))
        return

    processing_msg = await message.answer(_('generating_story', i18n))

    import random
    topic = random.choice(STORY_TOPICS)
    learning_lang = SUPPORTED_LANGUAGES[user_db['learning_lang']]['gemini_name']
    native_lang = SUPPORTED_LANGUAGES[user_db['native_lang']]['gemini_name']
    level = LEARNING_LEVELS[user_db['learning_level']]

    result = await gemini_service.generate_story(learning_lang, native_lang, level, topic)
    await processing_msg.delete()

    if not result or not result.get('story'):
        await message.answer(_('generation_error', i18n))
        await show_learning_menu(message, i18n, user_db, state)
        return

    title = html.escape(result.get('title', ''))
    story = html.escape(result.get('story', ''))
    translation = html.escape(result.get('story_translation', ''))
    questions = result.get('questions', [])

    await state.set_state(AppStates.in_story_mode)
    await state.update_data(
        story_questions=questions,
        story_q_index=0,
        story_correct=0,
    )

    text = (
        f"📖 <b>{title}</b>\n\n"
        f"{story}\n\n"
        f"<i>— {translation}</i>"
    )
    await send_safe_html(
        message, text,
        reply_markup=get_dynamic_reply_keyboard(
            [_('start_story_quiz', i18n)], i18n, 'back_to_learn_menu'
        )
    )


@learning_router.message(AppStates.in_story_mode, F.text)
async def handle_story_start_quiz(message: Message, state: FSMContext, bot: Bot, user_db: dict):
    i18n = getattr(bot, 'i18n', {})
    data = await state.get_data()
    questions = data.get('story_questions', [])
    q_index = data.get('story_q_index', 0)

    start_texts = [i18n.get('start_story_quiz', '▶️ Start Quiz')]
    if message.text not in start_texts:
        return

    if not questions or q_index >= len(questions):
        await show_learning_menu(message, i18n, user_db, state)
        return

    await _show_story_question(message, i18n, state, questions, q_index)


async def _show_story_question(message, i18n, state, questions, q_index):
    q = questions[q_index]
    question = html.escape(q.get('question', ''))
    options = [html.escape(opt) for opt in q.get('options', [])]

    use_labels = any(len(opt) > 25 for opt in options)
    text = f"❓ <b>{q_index + 1}/{len(questions)}</b> {question}"

    if use_labels:
        labeled = "\n".join(f"<b>{chr(65+i)}:</b> {opt}" for i, opt in enumerate(options))
        text += f"\n\n{labeled}"
        reply_buttons = [chr(65+i) for i in range(len(options))]
    else:
        reply_buttons = options

    await state.set_state(AppStates.awaiting_story_quiz_answer)
    await state.update_data(
        story_q_options=options,
        story_use_labels=use_labels,
        story_correct_answer=html.escape(q.get('correct_answer_text', '')),
    )
    await message.answer(
        text,
        reply_markup=get_dynamic_reply_keyboard(reply_buttons, i18n, 'back_to_learn_menu')
    )


@learning_router.message(AppStates.awaiting_story_quiz_answer, F.text)
async def process_story_quiz_answer(message: Message, state: FSMContext, bot: Bot, user_db: dict):
    i18n = getattr(bot, 'i18n', {})
    data = await state.get_data()
    questions = data.get('story_questions', [])
    q_index = data.get('story_q_index', 0)
    correct_count = data.get('story_correct', 0)
    correct_answer = data.get('story_correct_answer', '')
    options = data.get('story_q_options', [])
    use_labels = data.get('story_use_labels', False)

    user_answer = message.text
    if use_labels and user_answer in ['A', 'B', 'C', 'D'] and options:
        idx = ord(user_answer) - ord('A')
        if 0 <= idx < len(options):
            user_answer = options[idx]

    is_correct = user_answer.strip().lower() == correct_answer.strip().lower()
    if is_correct:
        correct_count += 1
        await message.answer(f"✅ {_('correct', i18n)}")
    else:
        await message.answer(f"❌ {_('incorrect', i18n)} — ✅ <b>{correct_answer}</b>")

    next_index = q_index + 1
    await state.update_data(story_q_index=next_index, story_correct=correct_count)

    if next_index >= len(questions):
        # Quiz done
        await increment_user_stat(message.from_user.id, 'quizzes_passed_count')
        score_text = (
            f"🎉 <b>{_('story_quiz_done', i18n)}</b>\n"
            f"📊 {correct_count}/{len(questions)} {_('correct_answers', i18n)}"
        )
        await message.answer(
            score_text,
            reply_markup=get_dynamic_reply_keyboard(
                [i18n.get('story_mode_button', '📖 Story Mode')],
                i18n, 'back_to_learn_menu'
            )
        )
        await state.set_state(AppStates.in_learning_menu)
    else:
        await _show_story_question(message, i18n, state, questions, next_index)


# ─── Idiom of the Day ────────────────────────────────────────────────────────

@learning_router.message(
    AppStates.in_learning_menu,
    F.text.in_(get_all_translations("idiom_button", all_locales))
)
async def handle_idiom(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    i18n = getattr(bot, 'i18n', {})
    if user_db.get('learning_mode') != 'human':
        await message.answer(_('human_mode_only', i18n))
        return

    processing_msg = await message.answer(_('generating_idiom', i18n))
    learning_lang = SUPPORTED_LANGUAGES[user_db['learning_lang']]['gemini_name']
    native_lang = SUPPORTED_LANGUAGES[user_db['native_lang']]['gemini_name']

    result = await gemini_service.generate_idiom(learning_lang, native_lang)
    await processing_msg.delete()

    if not result or not result.get('idiom'):
        await message.answer(_('generation_error', i18n))
        await show_learning_menu(message, i18n, user_db, state)
        return

    idiom = html.escape(result.get('idiom', ''))
    literal = html.escape(result.get('literal_translation', ''))
    meaning = html.escape(result.get('meaning', ''))
    example = html.escape(result.get('example', ''))
    example_tr = html.escape(result.get('example_translation', ''))

    text = (
        f"💬 <b>{_('idiom_title', i18n)}</b>\n\n"
        f"🗣 <b>{idiom}</b>\n\n"
        f"📝 <i>{_('literal', i18n)}:</i> {literal}\n"
        f"💡 <i>{_('meaning', i18n)}:</i> {meaning}\n\n"
        f"📌 <i>{_('example', i18n)}:</i>\n"
        f"   <i>{example}</i>\n"
        f"   {example_tr}"
    )

    await send_safe_html(
        message, text,
        reply_markup=get_dynamic_reply_keyboard(
            [i18n.get('idiom_button', '💬 Idiom')], i18n, 'back_to_learn_menu'
        )
    )
    await state.set_state(AppStates.in_learning_menu)


# ─── Grammar Check ───────────────────────────────────────────────────────────

@learning_router.message(
    AppStates.in_learning_menu,
    F.text.in_(get_all_translations("grammar_check_button", all_locales))
)
async def handle_grammar_check_entry(message: Message, user_db: dict, state: FSMContext, bot: Bot):
    i18n = getattr(bot, 'i18n', {})
    if user_db.get('learning_mode') != 'human':
        await message.answer(_('human_mode_only', i18n))
        return

    await state.set_state(AppStates.in_grammar_check)
    learning_lang = SUPPORTED_LANGUAGES[user_db['learning_lang']]['display_name']
    await message.answer(
        _('grammar_check_prompt', i18n, lang=learning_lang),
        reply_markup=get_dynamic_reply_keyboard([], i18n, 'back_to_learn_menu')
    )


@learning_router.message(AppStates.in_grammar_check, F.text)
async def process_grammar_check(message: Message, state: FSMContext, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    processing_msg = await message.answer(_('checking_grammar', i18n))

    learning_lang = SUPPORTED_LANGUAGES[user_db['learning_lang']]['gemini_name']
    native_lang = SUPPORTED_LANGUAGES[user_db['native_lang']]['gemini_name']

    result = await gemini_service.check_grammar(message.text, learning_lang, native_lang)
    await processing_msg.delete()

    if not result:
        await message.answer(_('generation_error', i18n))
        await show_learning_menu(message, i18n, user_db, state)
        return

    has_errors = result.get('has_errors', False)
    corrected = html.escape(result.get('corrected_text', ''))
    errors = result.get('errors', [])
    feedback = html.escape(result.get('overall_feedback', ''))

    if not has_errors:
        text = f"✅ <b>{_('grammar_perfect', i18n)}</b>\n\n💬 {feedback}"
    else:
        text = f"📝 <b>{_('grammar_result', i18n)}</b>\n\n"
        text += f"✅ <b>{_('corrected', i18n)}:</b> <i>{corrected}</i>\n\n"
        if errors:
            text += f"🔍 <b>{_('errors_found', i18n)}:</b>\n"
            for err in errors[:5]:
                orig = html.escape(err.get('original', ''))
                fix = html.escape(err.get('correction', ''))
                expl = html.escape(err.get('explanation', ''))
                text += f"  • <s>{orig}</s> → <b>{fix}</b>\n    <i>{expl}</i>\n"
        text += f"\n💬 {feedback}"

    await send_safe_html(
        message, text,
        reply_markup=get_dynamic_reply_keyboard([], i18n, 'back_to_learn_menu')
    )


@learning_router.message(F.text.in_(get_all_translations("back_to_learn_menu", all_locales)))
async def handle_back_to_learn_menu(message: Message, user_db: dict, state: FSMContext):
    i18n = getattr(message.bot, 'i18n', {})
    await show_learning_menu(message, i18n, user_db, state)

@learning_router.message(AppStates.awaiting_learning_answer, F.text)
async def process_learning_answer(message: Message, state: FSMContext, user_db: dict):
    i18n = getattr(message.bot, 'i18n', {})
    user_answer = message.text
    data = await state.get_data()

    # Handle "Save Word" button
    save_texts = get_all_translations("save_word_button", all_locales)
    if user_answer in save_texts or user_answer == "💾 Save Word":
        word = data.get("original_text", "")
        translation = data.get("word_translation", "")
        lang = data.get("source_lang", "")
        if word and translation:
            saved = await save_word(message.from_user.id, word, translation, lang)
            if saved:
                await message.answer(_("word_saved", i18n, word=html.escape(word)))
            else:
                await message.answer(_("word_already_saved", i18n, word=html.escape(word)))
        await show_learning_menu(message, i18n, user_db, state)
        return

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

    # After feedback, offer to save the word
    word = data.get("original_text", "")
    translation = data.get("word_translation", "")
    if word and translation:
        buttons = [i18n.get("save_word_button", "💾 Save Word")]
        await message.answer(
            _("save_word_prompt", i18n, word=html.escape(word), translation=html.escape(translation)),
            reply_markup=get_dynamic_reply_keyboard(buttons, i18n, "back_to_learn_menu")
        )
    else:
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