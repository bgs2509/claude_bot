"""Обработка фотографий."""

import asyncio

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_rate_limit, track_usage
from claude_bot.services.claude import run_claude, send_long
from claude_bot.services.ocr import ocr_image
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

from . import download_file, safe_delete, send_files

router = Router(name="photo")


@router.message(F.photo)
async def handle_photo(
    message: Message,
    settings: Settings,
    state: AppState,
    storage: SessionStorage | None = None,
) -> None:
    uid = message.from_user.id
    wait = check_rate_limit(uid, settings, state)
    if wait > 0:
        await asyncio.sleep(wait)
        check_rate_limit(uid, settings, state)
    track_usage(uid, state)

    waiting = await message.answer("📷 Обрабатываю фото...")

    # Скачать фото (берём наибольшее разрешение)
    img_path = await download_file(message.bot, message.photo[-1].file_id, ".jpg")

    ocr_text = await ocr_image(img_path, state)

    caption = message.caption or "Проанализируй это изображение"
    prompt = (
        f"Пользователь отправил фото. OCR распознал текст:\n\n"
        f"```\n{ocr_text}\n```\n\n"
        f"Задача пользователя: {caption}"
    )

    await waiting.edit_text("⏳ Claude думает...")

    response = await run_claude(prompt, uid, settings, state, storage=storage)
    await send_long(message, response.text, settings.max_message_len)
    if response.files:
        await send_files(message, response.files)

    await safe_delete(waiting)
