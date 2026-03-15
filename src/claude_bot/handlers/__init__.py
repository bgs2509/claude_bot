"""Общие хелперы для хендлеров."""

import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from aiogram import Bot, types
from aiogram.types import FSInputFile, ReplyKeyboardMarkup

from claude_bot.config import Settings, get_user_projects_dir
from claude_bot.context import obs_output_var, obs_status_var
from claude_bot.errors import get_user_message
from claude_bot.keyboards import build_project_reply_keyboard
from claude_bot.services.claude import ClaudeResponse, run_claude, send_long
from claude_bot.services.speech import synthesize_speech
from claude_bot.state import AppState

if TYPE_CHECKING:
    from claude_bot.services.storage import SessionStorage

log = logging.getLogger("claude-bot.handlers")

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}


def _build_reply_kb(
    storage: "SessionStorage | None",
    settings: Settings,
    uid: int,
) -> ReplyKeyboardMarkup | None:
    """Собрать reply-клавиатуру с проектами если доступен storage."""
    if not storage:
        return None
    projects_dir = get_user_projects_dir(settings, uid)
    projects = storage.list_projects(projects_dir)
    user = storage.get_user(uid)
    return build_project_reply_keyboard(projects, user.active_project)


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
    app_state: AppState,
) -> None:
    """Отправить голосовой ответ если у пользователя включён голосовой режим."""
    if not app_state.user_voice_mode.get(uid, False):
        return
    mp3_path = await synthesize_speech(text, settings)
    if mp3_path:
        audio = FSInputFile(mp3_path)
        await message.answer_voice(audio)
        try:
            os.unlink(mp3_path)
        except OSError:
            pass


async def send_files(message: types.Message, files: list[Path]) -> None:
    """Отправить файлы пользователю. Изображения — как фото, остальное — как документы."""
    for file_path in files:
        if not file_path.exists():
            continue
        input_file = FSInputFile(file_path)
        if file_path.suffix.lower() in IMAGE_EXTENSIONS:
            await message.answer_photo(input_file)
        else:
            await message.answer_document(input_file)


async def safe_delete(message: types.Message) -> None:
    """Безопасное удаление сообщения (игнорирует ошибки)."""
    try:
        await message.delete()
    except Exception:
        pass


async def call_claude_safe(
    message: types.Message,
    waiting: types.Message,
    prompt: str,
    uid: int,
    settings: Settings,
    app_state: AppState,
    storage: "SessionStorage | None" = None,
) -> ClaudeResponse | None:
    """Вызвать run_claude с обработкой ошибок и cleanup waiting-сообщения.

    Возвращает ClaudeResponse или None при ошибке.
    """
    try:
        response = await run_claude(prompt, uid, settings, app_state, storage=storage)
        reply_markup = _build_reply_kb(storage, settings, uid)
        await send_long(message, response.text, settings.max_message_len, reply_markup=reply_markup)
        if response.files:
            await send_files(message, response.files)
        obs_status_var.set("claude_success")
        obs_output_var.set(response.text[:80])
        return response
    except Exception:
        log.error("Ошибка run_claude", exc_info=True)
        obs_status_var.set("claude_error")
        await message.answer(get_user_message("claude_error"))
        return None
    finally:
        await safe_delete(waiting)
