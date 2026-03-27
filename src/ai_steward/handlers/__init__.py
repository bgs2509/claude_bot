"""Общие хелперы для хендлеров."""

import logging
import os
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from aiogram import Bot, types
from aiogram.types import FSInputFile, ReplyKeyboardMarkup

from ai_steward.config import Settings, get_user_projects_dir
from ai_steward.context import obs_output_var, obs_status_var
from ai_steward.errors import get_user_message
from ai_steward.keyboards import build_project_reply_keyboard
from ai_steward.services.claude import ClaudeResponse, run_claude
from ai_steward.services.format_telegram import markdown_to_telegram_html
from ai_steward.services.pdf import text_to_pdf
from ai_steward.services.speech import synthesize_speech
from ai_steward.state import AppState

if TYPE_CHECKING:
    from ai_steward.services.storage import SessionStorage

log = logging.getLogger("ai-steward.handlers")

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


async def _send_html_or_plain(
    message: types.Message,
    text: str,
    reply_markup: types.ReplyKeyboardMarkup | None = None,
    project_tag: str = "",
) -> None:
    """Отправить сообщение как HTML, при ошибке — plain text."""
    formatted = markdown_to_telegram_html(text)
    try:
        await message.answer(project_tag + formatted, parse_mode="HTML", reply_markup=reply_markup)
    except Exception:
        log.debug("HTML parse failed, fallback to plain", exc_info=True)
        # Убрать <code> теги из project_tag для plain text
        plain_tag = project_tag.replace("<code>", "").replace("</code>", "") if project_tag else ""
        await message.answer(plain_tag + text, reply_markup=reply_markup)


async def send_long(
    message: types.Message,
    text: str,
    max_len: int = 4000,
    reply_markup: types.ReplyKeyboardMarkup | None = None,
    project_tag: str = "",
) -> None:
    """Отправка ответа. Если > max_len — первый чанк + .md файл."""
    if not text.strip():
        text = "(пустой ответ)"

    if len(text) <= max_len:
        await _send_html_or_plain(message, text, reply_markup=reply_markup, project_tag=project_tag)
        return

    # Первый чанк + файл с полным ответом
    preview = text[:max_len]
    await _send_html_or_plain(message, preview, project_tag=project_tag)

    pdf_path = text_to_pdf(text)
    doc = FSInputFile(pdf_path, filename="response.pdf")
    await message.answer_document(
        doc, caption="Полный ответ в файле", reply_markup=reply_markup,
    )
    os.unlink(pdf_path)


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
        log.debug("safe_delete failed", exc_info=True)


async def call_claude_safe(
    message: types.Message,
    waiting: types.Message,
    prompt: str,
    uid: int,
    settings: Settings,
    app_state: AppState,
    storage: "SessionStorage | None" = None,
    project_tag: str = "",
) -> ClaudeResponse | None:
    """Вызвать run_claude с обработкой ошибок и cleanup waiting-сообщения.

    Args:
        message: Сообщение пользователя для ответа.
        waiting: Сообщение-индикатор ожидания (удаляется в finally).
        prompt: Текст запроса для Claude.
        uid: Telegram user ID.
        settings: Конфигурация бота.
        app_state: In-memory состояние приложения.
        storage: Хранилище сессий (опционально).
        project_tag: HTML-тег проекта для префикса сообщений.

    Returns:
        ClaudeResponse или None при ошибке.
    """
    try:
        response = await run_claude(prompt, uid, settings, app_state, storage=storage)
        reply_markup = _build_reply_kb(storage, settings, uid)
        await send_long(message, response.text, settings.max_message_len, reply_markup=reply_markup, project_tag=project_tag)
        if response.files:
            await send_files(message, response.files)
        obs_status_var.set("claude_success")
        obs_output_var.set(response.text[:80])
        return response
    except Exception:
        log.error("Ошибка run_claude", exc_info=True)
        obs_status_var.set("claude_error")
        await message.answer(project_tag + get_user_message("claude_error"), parse_mode="HTML")
        return None
    finally:
        await safe_delete(waiting)
