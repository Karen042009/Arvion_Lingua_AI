import logging
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.enums import ParseMode

async def send_safe_html(message: Message, text: str, **kwargs):
    try:
        await message.answer(text, parse_mode=ParseMode.HTML, **kwargs)
    except TelegramBadRequest as e:
        if "can't parse entities" in e.message:
            logging.warning(
                f"HTML parse failed, falling back to plain text. Error: {e}"
            )
            await message.answer(text, parse_mode=None, **kwargs)
        else:
            raise e

async def edit_safe_html(message: Message, text: str, **kwargs):
    try:
        await message.edit_text(text, parse_mode=ParseMode.HTML, **kwargs)
    except TelegramBadRequest as e:
        if "can't parse entities" in e.message:
            logging.warning(
                f"HTML edit failed, falling back to plain text. Error: {e}"
            )
            await message.edit_text(text, parse_mode=None, **kwargs)
        elif "message is not modified" in e.message:
            logging.info("Message not modified, skipping edit.")
        else:
            raise e