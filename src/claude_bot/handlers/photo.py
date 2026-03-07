"""Обработка фотографий."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_rate_limit, track_usage
from claude_bot.services.ocr import ocr_image
from claude_bot.services.storage import SessionStorage
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

    log.info("Фото")
    waiting = await message.answer("📷 Обрабатываю фото...")

    # Скачать фото (берём наибольшее разрешение)
    img_path = await download_file(message.bot, message.photo[-1].file_id, ".jpg")

    ocr_text = await ocr_image(img_path, app_state)

    caption = message.caption or "Проанализируй это изображение"
    prompt = (
        f"Пользователь отправил фото. OCR распознал текст:\n\n"
        f"```\n{ocr_text}\n```\n\n"
        f"Задача пользователя: {caption}"
    )

    await waiting.edit_text("⏳ Claude думает...")

    await call_claude_safe(
        message, waiting, prompt, uid, settings, app_state, storage,
    )
