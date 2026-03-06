"""Обработка фотографий."""

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_limit
from claude_bot.services.claude import run_claude, send_long
from claude_bot.services.ocr import ocr_image
from claude_bot.state import AppState

from . import download_file, safe_delete

router = Router(name="photo")


@router.message(F.photo)
async def handle_photo(message: Message, settings: Settings, state: AppState) -> None:
    uid = message.from_user.id
    if not check_limit(uid, settings, state):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

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

    result = await run_claude(prompt, uid, settings, state)
    await send_long(message, result, settings.max_message_len)

    await safe_delete(waiting)
