"""Общие хелперы для хендлеров."""

import os
import tempfile

from aiogram import Bot, types
from aiogram.types import FSInputFile

from claude_bot.config import Settings
from claude_bot.state import AppState
from claude_bot.services.speech import synthesize_speech


async def download_file(bot: Bot, file_id: str, suffix: str) -> str:
    """Скачать файл из Telegram во временный файл."""
    file = await bot.get_file(file_id)
    tmp_path = tempfile.mktemp(suffix=suffix)
    await bot.download_file(file.file_path, tmp_path)
    return tmp_path


async def send_voice_if_enabled(
    message: types.Message,
    text: str,
    uid: int,
    settings: Settings,
    state: AppState,
) -> None:
    """Отправить голосовой ответ если у пользователя включён голосовой режим."""
    if not state.user_voice_mode.get(uid, False):
        return
    mp3_path = await synthesize_speech(text, settings)
    if mp3_path:
        audio = FSInputFile(mp3_path)
        await message.answer_voice(audio)
        try:
            os.unlink(mp3_path)
        except OSError:
            pass


async def safe_delete(message: types.Message) -> None:
    """Безопасное удаление сообщения (игнорирует ошибки)."""
    try:
        await message.delete()
    except Exception:
        pass
