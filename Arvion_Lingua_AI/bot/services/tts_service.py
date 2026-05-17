import io
import asyncio
import logging
from gtts import gTTS
from aiogram.types import BufferedInputFile

async def text_to_speech_file(
    text: str, lang: str = 'en'
) -> BufferedInputFile | None:
    if not text:
        return None
    try:
        loop = asyncio.get_event_loop()
        mp3_fp = io.BytesIO()

        def blocking_tts_task():
            try:
                tts = gTTS(text=text, lang=lang, slow=False)
                tts.write_to_fp(mp3_fp)
                mp3_fp.seek(0)
                return True
            except Exception as e_tts:
                logging.error(f"gTTS error for lang '{lang}': {e_tts}")
                return False

        success = await loop.run_in_executor(None, blocking_tts_task)
        if not success:
            return None

        return BufferedInputFile(mp3_fp.read(), filename="speech.mp3")
    except Exception as e:
        logging.error(f"Error in text_to_speech_file: {e}")
        return None