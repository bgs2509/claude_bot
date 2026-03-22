"""Обработка фотографий — сохранение в проект + OCR + передача Claude."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from ai_steward.config import Settings
from ai_steward.errors import get_user_message
from ai_steward.middlewares.auth import check_rate_limit, track_usage
from ai_steward.services.claude import get_project_dir
from ai_steward.services.ocr import ocr_image
from ai_steward.services.storage import SessionStorage
from ai_steward.services.upload import (
    build_file_prompt,
    generate_photo_filename,
    save_uploaded_file,
)
from ai_steward.state import AppState

from . import call_claude_safe, download_file

router = Router(name="photo")
log = logging.getLogger("ai-steward.photo")


@router.message(F.photo)
async def handle_photo(
    message: Message,
    settings: Settings,
    app_state: AppState,
    storage: SessionStorage | None = None,
    project_tag: str = "",
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
        await message.answer(project_tag + get_user_message("no_active_project"), parse_mode="HTML")
        return

    filename = generate_photo_filename()
    caption = message.caption or "Проанализируй это изображение"

    log.info("Фото → %s", filename)
    waiting = await message.answer(project_tag + "📷 Сохраняю фото в проект...", parse_mode="HTML")

    tmp_path = await download_file(message.bot, message.photo[-1].file_id, ".jpg")

    # Сохранить (auto-suffix при маловероятной коллизии)
    saved = save_uploaded_file(tmp_path, project_dir, filename, overwrite=False)

    # OCR из сохранённого файла (без удаления)
    ocr_text = await ocr_image(str(saved), app_state, delete=False)

    prompt = build_file_prompt(
        filename, saved, is_binary=True, caption=caption, ocr_text=ocr_text,
    )

    await waiting.edit_text(project_tag + "⏳ Claude думает...", parse_mode="HTML")
    await call_claude_safe(message, waiting, prompt, uid, settings, app_state, storage, project_tag=project_tag)
