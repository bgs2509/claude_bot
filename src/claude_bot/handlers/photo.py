"""Обработка фотографий — сохранение в проект + OCR + передача Claude."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.errors import get_user_message
from claude_bot.middlewares.auth import check_rate_limit, track_usage
from claude_bot.services.claude import get_project_dir
from claude_bot.services.ocr import ocr_image
from claude_bot.services.storage import SessionStorage
from claude_bot.services.upload import (
    build_file_prompt,
    generate_photo_filename,
    save_uploaded_file,
)
from claude_bot.state import AppState

from . import call_claude_safe, download_file

router = Router(name="photo")
log = logging.getLogger("claude-bot.photo")


@router.message(F.photo)
async def handle_photo(
    message: Message,
    settings: Settings,
    app_state: AppState,
    storage: SessionStorage | None = None,
) -> None:
    uid = message.from_user.id
    wait = check_rate_limit(uid, settings, app_state)
    if wait > 0:
        await asyncio.sleep(wait)
        check_rate_limit(uid, settings, app_state)
    track_usage(uid, app_state)

    try:
        project_dir = get_project_dir(settings, storage, uid)
    except ValueError:
        await message.answer(get_user_message("no_active_project"))
        return

    filename = generate_photo_filename()
    caption = message.caption or "Проанализируй это изображение"

    log.info("Фото → %s", filename)
    waiting = await message.answer("📷 Сохраняю фото в проект...")

    tmp_path = await download_file(message.bot, message.photo[-1].file_id, ".jpg")

    # Сохранить (auto-suffix при маловероятной коллизии)
    saved = save_uploaded_file(tmp_path, project_dir, filename, overwrite=False)

    # OCR из сохранённого файла (без удаления)
    ocr_text = await ocr_image(str(saved), app_state, delete=False)

    prompt = build_file_prompt(
        filename, saved, is_binary=True, caption=caption, ocr_text=ocr_text,
    )

    await waiting.edit_text("⏳ Claude думает...")
    await call_claude_safe(message, waiting, prompt, uid, settings, app_state, storage)
