import json
import logging
from pathlib import Path
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User
from database.db_utils import get_or_create_user

class Localization(BaseMiddleware):
    def __init__(self, locales_dir: Path):
        self.locales = {}
        for file in locales_dir.iterdir():
            if file.suffix == ".json":
                lang_code = file.stem
                with open(file, 'r', encoding='utf-8') as f:
                    self.locales[lang_code] = json.load(f)

        self.default_lang_texts = self.locales.get('en', {})
        if not self.default_lang_texts:
            logging.error("Default locale 'en.json' not found or is empty!")

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        user: User | None = data.get('event_from_user')
        if not user:
            data['i18n'] = self.default_lang_texts.copy()
            return await handler(event, data)

        user_db_data = await get_or_create_user(user.id)
        lang_code = user_db_data.get('interface_lang', 'en')

        current_lang_texts = self.locales.get(
            lang_code, self.default_lang_texts
        )
        merged_texts = self.default_lang_texts.copy()
        merged_texts.update(current_lang_texts)

        data['i18n'] = merged_texts
        data['user_db'] = user_db_data

        bot = data.get('bot')
        if bot:
            bot.i18n = merged_texts

        return await handler(event, data)

def _(key: str, i18n: dict, **kwargs) -> str:
    return i18n.get(key, f"_{key}_").format(**kwargs)

def get_all_translations(key: str, locales: dict) -> list[str]:
    translations = set()
    for lang_code, texts in locales.items():
        if key in texts:
            translations.add(texts[key])
    return list(translations) if translations else [f"_{key}_"]