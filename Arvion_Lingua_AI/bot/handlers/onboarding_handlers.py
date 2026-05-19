"""
Onboarding flow for new users.
Steps: interface language → learning mode → learning subject → level → done
"""
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message

from bot.keyboards.reply import get_dynamic_reply_keyboard, get_main_reply_keyboard
from bot.middlewares.localization import _
from bot.services.gemini_service import GeminiService
from config import (
    SUPPORTED_LANGUAGES, LEARNING_LEVELS,
    SUPPORTED_PROGRAMMING_LANGUAGES, PROGRAMMING_LEVELS
)
from database.db_utils import (
    get_or_create_user, update_user_setting, set_onboarding_complete
)

onboarding_router = Router()


class OnboardingStates(StatesGroup):
    step_interface_lang = State()
    step_learning_mode = State()
    step_learning_subject = State()
    step_level = State()


def _find_lang_key(display_name: str) -> str | None:
    for code, data in SUPPORTED_LANGUAGES.items():
        if data["display_name"] == display_name:
            return code
    return None


def _find_prog_key(display_name: str) -> str | None:
    for code, data in SUPPORTED_PROGRAMMING_LANGUAGES.items():
        if data["display_name"] == display_name:
            return code
    return None


@onboarding_router.message(CommandStart())
async def cmd_start_onboarding(message: Message, state: FSMContext, user_db: dict):
    """Entry point: if onboarding not done, start it; otherwise show main menu."""
    if user_db.get("onboarding_complete", 0):
        # Already onboarded — go to main menu via common handler
        from bot.handlers.common_handlers import navigate_to_main_menu
        i18n = getattr(message.bot, "i18n", {})
        await navigate_to_main_menu(message, i18n, state)
        return

    await state.clear()
    await state.set_state(OnboardingStates.step_interface_lang)

    lang_names = [v["display_name"] for v in SUPPORTED_LANGUAGES.values()]
    await message.answer(
        "👋 <b>Welcome to Arvion Lingua AI!</b>\n\n"
        "Let's set up your experience in 4 quick steps.\n\n"
        "<b>Step 1 / 4 — Choose your interface language:</b>",
        reply_markup=get_dynamic_reply_keyboard(lang_names, {})
    )


@onboarding_router.message(OnboardingStates.step_interface_lang)
async def onboarding_set_interface_lang(message: Message, state: FSMContext):
    lang_code = _find_lang_key(message.text)
    if not lang_code:
        await message.answer("Please choose a language from the list.")
        return

    await update_user_setting(message.from_user.id, "interface_lang", lang_code)
    await state.update_data(interface_lang=lang_code)

    # Reload i18n for the chosen language
    from bot.middlewares.localization import Localization
    from pathlib import Path
    locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
    loc = Localization(locales_dir)
    i18n = loc.locales.get(lang_code, loc.default_lang_texts)
    message.bot.i18n = i18n

    await state.set_state(OnboardingStates.step_learning_mode)
    modes = [i18n.get("mode_human", "Human Languages"), i18n.get("mode_programming", "Programming")]
    await message.answer(
        _("onboarding_step2", i18n),
        reply_markup=get_dynamic_reply_keyboard(modes, i18n)
    )


@onboarding_router.message(OnboardingStates.step_learning_mode)
async def onboarding_set_mode(message: Message, state: FSMContext):
    i18n = getattr(message.bot, "i18n", {})
    data = await state.get_data()
    lang_code = data.get("interface_lang", "en")

    from bot.middlewares.localization import Localization
    from pathlib import Path
    locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
    loc = Localization(locales_dir)
    i18n = loc.locales.get(lang_code, loc.default_lang_texts)

    human_text = i18n.get("mode_human", "Human Languages")
    prog_text = i18n.get("mode_programming", "Programming")

    if message.text == human_text:
        mode = "human"
    elif message.text == prog_text:
        mode = "programming"
    else:
        await message.answer(_("unknown_command", i18n))
        return

    await update_user_setting(message.from_user.id, "learning_mode", mode)
    await state.update_data(learning_mode=mode)
    await state.set_state(OnboardingStates.step_learning_subject)

    if mode == "human":
        subjects = [v["display_name"] for v in SUPPORTED_LANGUAGES.values()]
        prompt = _("onboarding_step3_human", i18n)
    else:
        subjects = [v["display_name"] for v in SUPPORTED_PROGRAMMING_LANGUAGES.values()]
        prompt = _("onboarding_step3_prog", i18n)

    await message.answer(prompt, reply_markup=get_dynamic_reply_keyboard(subjects, i18n))


@onboarding_router.message(OnboardingStates.step_learning_subject)
async def onboarding_set_subject(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("interface_lang", "en")
    mode = data.get("learning_mode", "human")

    from bot.middlewares.localization import Localization
    from pathlib import Path
    locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
    loc = Localization(locales_dir)
    i18n = loc.locales.get(lang_code, loc.default_lang_texts)

    if mode == "human":
        subject_code = _find_lang_key(message.text)
        if not subject_code:
            await message.answer(_("unknown_command", i18n))
            return
        await update_user_setting(message.from_user.id, "learning_lang", subject_code)
        levels = list(LEARNING_LEVELS.values())
    else:
        subject_code = _find_prog_key(message.text)
        if not subject_code:
            await message.answer(_("unknown_command", i18n))
            return
        await update_user_setting(message.from_user.id, "programming_lang", subject_code)
        levels = list(PROGRAMMING_LEVELS.values())

    await state.update_data(subject_code=subject_code)
    await state.set_state(OnboardingStates.step_level)
    await message.answer(
        _("onboarding_step4", i18n),
        reply_markup=get_dynamic_reply_keyboard(levels, i18n)
    )


@onboarding_router.message(OnboardingStates.step_level)
async def onboarding_set_level(message: Message, state: FSMContext):
    data = await state.get_data()
    lang_code = data.get("interface_lang", "en")
    mode = data.get("learning_mode", "human")

    from bot.middlewares.localization import Localization
    from pathlib import Path
    locales_dir = Path(__file__).resolve().parent.parent.parent / "locales"
    loc = Localization(locales_dir)
    i18n = loc.locales.get(lang_code, loc.default_lang_texts)

    if mode == "human":
        level_code = next((k for k, v in LEARNING_LEVELS.items() if v == message.text), None)
        if not level_code:
            await message.answer(_("unknown_command", i18n))
            return
        await update_user_setting(message.from_user.id, "learning_level", level_code)
    else:
        level_code = next((k for k, v in PROGRAMMING_LEVELS.items() if v == message.text), None)
        if not level_code:
            await message.answer(_("unknown_command", i18n))
            return
        await update_user_setting(message.from_user.id, "programming_level", level_code)

    await set_onboarding_complete(message.from_user.id)
    await state.clear()

    from bot.states.app_states import AppStates
    await state.set_state(AppStates.idle)

    await message.answer(
        _("onboarding_done", i18n),
        reply_markup=get_main_reply_keyboard(i18n)
    )
