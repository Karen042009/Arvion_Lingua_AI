import google.generativeai as genai
import logging
import json
import io
import html
import asyncio
from PIL import Image
from config import GEMINI_API_KEY, GEMINI_MODEL
from database.db_utils import get_chat_history, add_to_chat_history

# Proxy-ի կարգավորում այստեղ այլևս պետք չէ։
# Գրադարանը կոնֆիգուրացվում է պարզ եղանակով։
genai.configure(api_key=GEMINI_API_KEY)


class GeminiService:
    def __init__(self):
        self.api_key = GEMINI_API_KEY
        self.default_model_name = GEMINI_MODEL
        self.ranked_models = []
        self._initialize_models()

    def _initialize_models(self):
        """Fetches available models and ranks them by capability."""
        try:
            available_models = [
                m.name for m in genai.list_models()
                if 'generateContent' in m.supported_generation_methods
            ]
            
            # Հերթականություն՝ Pro (ամենալավը), Flash (արագ), այլ
            priority_patterns = [
                "gemini-3.1-pro",
                "gemini-3-pro",
                "gemini-2.5-pro",
                "gemini-2.0-pro",
                "gemini-1.5-pro",
                "gemini-3.1-flash",
                "gemini-3-flash",
                "gemini-2.5-flash",
                "gemini-2.0-flash",
                "gemini-1.5-flash",
                "gemini-pro",
                "gemini-flash"
            ]
            
            seen = set()
            for pattern in priority_patterns:
                for m_name in available_models:
                    if pattern in m_name and m_name not in seen:
                        self.ranked_models.append(m_name)
                        seen.add(m_name)
            
            # Ավելացնում ենք մնացած մոդելները, որոնք ցուցակում չկային
            for m_name in available_models:
                if m_name not in seen:
                    self.ranked_models.append(m_name)
            
            logging.info(f"Ranked models: {self.ranked_models}")
        except Exception as e:
            logging.error(f"Error listing models: {e}")
            self.ranked_models = [self.default_model_name]

    async def _safe_generate(
        self, prompt, use_json_config: bool = True, temperature: float = 0.4
    ) -> str | None:
        # Փորձում ենք մոդելները՝ սկսած լավագույնից
        models_to_try = self.ranked_models if self.ranked_models else [self.default_model_name]
        
        for model_name in models_to_try:
            try:
                model = genai.GenerativeModel(model_name)
                config_params = {"temperature": temperature}
                if use_json_config:
                    config_params["response_mime_type"] = "application/json"

                config = genai.GenerationConfig(**config_params)
                response = await model.generate_content_async(
                    prompt, generation_config=config
                )

                if not response.candidates:
                    logging.warning(f"Model {model_name} returned no candidates.")
                    continue
                
                return response.text.strip()
            except Exception as e:
                logging.error(f"Gemini API error with model {model_name}: {e}")
                # Անցնում ենք հաջորդ մոդելին
                continue
        
        return None

    def _parse_json_response(self, response_text: str) -> dict | None:
        try:
            return json.loads(response_text)
        except json.JSONDecodeError as e:
            logging.error(f"Failed to parse Gemini JSON: {e}\n{response_text}")
            return None

    async def get_text_from_image(
        self, image_bytes: io.BytesIO, target_lang: str
    ) -> dict | None:
        try:
            img = Image.open(image_bytes)
        except Exception as e:
            logging.error(f"Pillow could not open image bytes: {e}")
            return None
        prompt = [
            (
                f"Analyze this image. Identify all text. Then, translate it to "
                f"{target_lang}. Format as JSON: "
                f'{{"found_text": "...", "translated_text": "...", "detected_language_name": "..."}}'
            ),
            img
        ]
        response_str = await self._safe_generate(prompt, temperature=0.1)
        if not response_str:
            return None
        return self._parse_json_response(response_str)

    async def translate_text(
        self, text: str, target_language: str, source_language: str = "auto"
    ) -> dict | None:
        prompt = (
            f'Translate "{text}" into {target_language}. Source language is '
            f'{source_language}. Respond in JSON: '
            f'{{"detected_language_name": "...", "translated_text": "..."}}'
        )
        response_str = await self._safe_generate(prompt, temperature=0.2)
        if not response_str:
            return None
        return self._parse_json_response(response_str)

    async def get_learning_item(
        self, item_type: str, mode: str, lang_info: dict, level: str,
        recent_items: list | None = None
    ) -> dict | None:
        recent_prompt = ""
        if recent_items:
            items_str = ", ".join(f'"{item}"' for item in recent_items)
            recent_prompt = (
                "\nIMPORTANT: Do not generate any of the following, which the "
                f"user has seen: {items_str}."
            )

        academic_prompt = (
            "\nEnsure the explanation is academically sound, clear, and "
            "suitable for a university-level student, but adapt the core "
            "complexity to the user's selected proficiency level."
        )

        if mode == 'human':
            prompt = self._get_human_lang_prompt(
                item_type, lang_info, level, recent_prompt
            )
        elif mode == 'programming':
            prompt = self._get_programming_lang_prompt(
                item_type, lang_info, level, recent_prompt, academic_prompt
            )
        else:
            return None

        # Quiz needs lower temperature for reliable JSON structure
        temperature = 0.5 if item_type == 'quiz' else 0.95
        response_str = await self._safe_generate(prompt, temperature=temperature)
        if not response_str:
            return None
        return self._parse_json_response(response_str)

    def _get_human_lang_prompt(
        self, item_type: str, lang_info: dict, level: str, recent_prompt: str
    ) -> str | None:
        native, learning = lang_info['native'], lang_info['learning']
        if item_type == 'word':
            return (
                f"Generate one interesting word in {learning} for a {level} "
                f"learner. Provide its translation in {native}.{recent_prompt}\n"
                f"JSON response: {{\"item\": \"...\", \"translation\": \"...\"}}"
            )
        if item_type == 'quiz':
            return (
                f"Create a multiple-choice quiz question about {learning} for a {native} "
                f"speaker at {level} level.{recent_prompt}\n"
                f"IMPORTANT: The value of 'correct_answer_text' MUST be copied EXACTLY, "
                f"character-for-character, from one of the strings in the 'options' array.\n"
                f"JSON response: {{\"question\": \"...\", \"options\": [\"option A text\", \"option B text\", \"option C text\", \"option D text\"], "
                f"\"correct_answer_text\": \"<copy exact text of correct option here>\"}}"
            )
        return None

    def _get_programming_lang_prompt(
        self, item_type: str, lang_info: dict, level: str,
        recent_prompt: str, academic_prompt: str
    ) -> str | None:
        prog_lang = lang_info['programming']
        interface_lang = lang_info.get('interface_lang_name', 'English')
        lang_instruction = (
            f"CRITICAL INSTRUCTION: The entire response MUST be exclusively in "
            f"the {interface_lang} language. DO NOT mix languages. Use correct "
            "and natural-sounding terminology."
        )

        if item_type == 'concept':
            return (
                f"Generate a core concept for a {prog_lang} developer at "
                f"'{level}' level. {academic_prompt}{recent_prompt} "
                f"{lang_instruction}\nProvide an explanation and a code example."
                f"\nJSON response: {{\"item\": \"...\", \"explanation\": \"...\", "
                f"\"code_example\": \"...\"}}"
            )
        if item_type == 'quiz':
            return (
                f"Create a multiple-choice quiz question about {prog_lang} for a developer at '{level}' "
                f"level. {academic_prompt}{recent_prompt} {lang_instruction}\n"
                f"IMPORTANT: The value of 'correct_answer_text' MUST be copied EXACTLY, "
                f"character-for-character, from one of the strings in the 'options' array. "
                f"Do NOT paraphrase or summarize it.\n"
                f"JSON response: {{\"question\": \"...\", \"options\": [\"option A text\", \"option B text\", \"option C text\", \"option D text\"], "
                f"\"correct_answer_text\": \"<copy exact text of correct option here>\"}}"
            )
        return None

    async def get_fun_fact(
        self, mode: str, subject: str, interface_lang: str
    ) -> str | None:
        lang_instruction = f"CRITICAL: The fact MUST be in {interface_lang}."
        if mode == 'human':
            prompt = (
                f"Tell me one surprising, fun fact about the country/culture "
                f"of the {subject} language. {lang_instruction}"
            )
        else:
            prompt = (
                f"Tell me one surprising, fun fact about the history or a "
                f"feature of {subject}. {lang_instruction}"
            )

        response_str = await self._safe_generate(
            prompt, use_json_config=False, temperature=1.0
        )
        return html.unescape(response_str) if response_str else None

    async def evaluate_user_answer(
        self, original_text: str, user_translation: str,
        source_lang: str, target_lang: str
    ) -> str | None:
        prompt = (
            f'Original: "{original_text}" ({source_lang}). User translation: '
            f'"{user_translation}" ({target_lang}). Provide brief feedback in '
            f'{target_lang}.\nJSON response: {{"feedback": "..."}}'
        )
        response_str = await self._safe_generate(prompt, temperature=0.5)
        if not response_str:
            return None
        data = self._parse_json_response(response_str)
        return data.get("feedback") if data else None

    async def chat_with_ai(
        self, user_id: int, user_prompt: str,
        persona: str | None = None
    ) -> str:
        if persona is None:
            persona = "You are a helpful and friendly AI language tutor."

        history = await get_chat_history(user_id)
        current_chat_history = history + [{"role": "user", "parts": [{"text": user_prompt}]}]

        models_to_try = self.ranked_models if self.ranked_models else [self.default_model_name]
        
        for model_name in models_to_try:
            try:
                chat_model = genai.GenerativeModel(
                    model_name,
                    system_instruction=persona
                )
                
                if model_name == models_to_try[0]: # Միայն առաջին անգամ ավելացնենք history-ն
                    await add_to_chat_history(user_id, 'user', user_prompt)
                
                response = await chat_model.generate_content_async(current_chat_history)

                if response.candidates and response.candidates[0].content.parts:
                    response_text = response.text.strip()
                    await add_to_chat_history(user_id, 'model', response_text)
                    return response_text
                
                logging.warning(f"Model {model_name} in chat returned no candidates.")
            except Exception as e:
                logging.error(f"Gemini chat error with model {model_name} for user {user_id}: {e}")
                continue

        return "An error occurred with the AI service. Please try again."

    async def transcribe_audio(self, audio_data: bytes, mime_type: str = "audio/ogg") -> str | None:
        """Transcribes audio data to text using Gemini."""
        # Փորձում ենք մոդելները՝ սկսած Flash տարբերակներից, քանի որ դրանք լավագույնն են մուլտիմեդիայի համար
        models_to_try = [m for m in self.ranked_models if "flash" in m.lower()] + \
                        [m for m in self.ranked_models if "pro" in m.lower()]
        
        if not models_to_try:
            models_to_try = self.ranked_models if self.ranked_models else [self.default_model_name]

        for model_name in models_to_try:
            try:
                # Մուլտիմեդիա (աուդիո) աշխատանքի համար միայն 1.5 կամ ավելի նոր մոդելներն են պիտանի
                if not any(ver in model_name for ver in ["1.5", "2.0", "2.5", "3.0", "3.1"]):
                    continue

                model = genai.GenerativeModel(model_name)
                prompt = "Please transcribe this audio exactly as it is spoken. Only output the transcription text."
                
                response = await model.generate_content_async([
                    prompt,
                    {
                        "mime_type": mime_type,
                        "data": audio_data
                    }
                ])
                
                if response.candidates:
                    return response.text.strip()
                
                logging.warning(f"Transcription model {model_name} returned no candidates.")
            except Exception as e:
                logging.error(f"Audio transcription error with model {model_name}: {e}")
                # Անցնում ենք հաջորդին
                continue
        
        return None

    async def score_pronunciation(
        self, target_word: str, transcribed_text: str, language: str
    ) -> dict | None:
        """Compare user's spoken word with target and return accuracy score."""
        prompt = (
            f'The user was asked to pronounce the word "{target_word}" in {language}. '
            f'The speech recognition transcribed: "{transcribed_text}". '
            f'Compare them phonetically and semantically. '
            f'Give a score from 0 to 100 and brief feedback. '
            f'JSON: {{"score": 85, "feedback": "...", "correct": true}}'
        )
        response_str = await self._safe_generate(prompt, temperature=0.3)
        if not response_str:
            return None
        return self._parse_json_response(response_str)

    async def get_word_of_the_day(
        self, learning_lang: str, native_lang: str, level: str
    ) -> dict | None:
        """Generate a word of the day with example sentence."""
        prompt = (
            f'Generate a "Word of the Day" in {learning_lang} for a {level} learner. '
            f'Provide translation in {native_lang}, an example sentence in {learning_lang}, '
            f'and its translation. '
            f'JSON: {{"word": "...", "translation": "...", "example": "...", "example_translation": "...", "part_of_speech": "..."}}'
        )
        response_str = await self._safe_generate(prompt, temperature=0.9)
        if not response_str:
            return None
        return self._parse_json_response(response_str)

    async def summarize_conversation(
        self, history: list, interface_lang: str
    ) -> str | None:
        """Analyze a chat session and return a learning summary."""
        if not history:
            return None

        flat = "\n".join(
            f"{msg['role'].upper()}: {msg['parts'][0]['text']}"
            for msg in history
            if msg.get("parts")
        )
        prompt = (
            f"Analyze this language learning conversation and provide a brief summary in {interface_lang}.\n"
            f"Include: vocabulary used, grammar patterns, mistakes made, and suggestions.\n"
            f"Keep it encouraging and concise (max 5 bullet points).\n\n"
            f"Conversation:\n{flat[:3000]}"
        )
        return await self._safe_generate(prompt, use_json_config=False, temperature=0.5)
