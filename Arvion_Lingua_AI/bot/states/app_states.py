from aiogram.fsm.state import State, StatesGroup

class AppStates(StatesGroup):
    idle = State()

    # Settings states
    in_settings = State()
    awaiting_interface_lang = State()
    awaiting_native_lang = State()
    awaiting_learning_mode = State()
    awaiting_learning_subject = State()
    awaiting_level = State()

    # Translation states
    in_translation_mode = State()
    awaiting_source_lang = State()
    awaiting_target_lang = State()
    awaiting_tts_choice = State()

    # Learning states
    in_learning_menu = State()
    awaiting_learning_answer = State()
    awaiting_quiz_answer = State()

    # Chat states
    in_chat_menu = State()
    in_chat = State()
    in_roleplay = State()
    awaiting_roleplay_scenario = State()