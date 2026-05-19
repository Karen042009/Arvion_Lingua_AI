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

    # Pronunciation states
    awaiting_pronunciation = State()

    # Flashcard review states
    in_flashcard_review = State()
    awaiting_flashcard_answer = State()

    # Story mode states
    in_story_mode = State()
    awaiting_story_quiz_answer = State()

    # Grammar check state
    in_grammar_check = State()

    # Fill in the blank state
    awaiting_fill_blank_answer = State()

    # Game states
    in_word_scramble = State()
    awaiting_scramble_answer = State()
    in_hangman = State()
    awaiting_hangman_letter = State()
    in_speed_round = State()
    awaiting_speed_answer = State()

    # Grammar Guide state
    in_grammar_guide = State()

    # Culture Corner state
    in_culture_corner = State()