"""Обработка документов (текстовые файлы)."""

import os
import tempfile

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_limit
from claude_bot.services.claude import run_claude, send_long
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

from . import safe_delete, send_files

router = Router(name="document")


@router.message(F.document)
async def handle_document(
    message: Message,
    settings: Settings,
    state: AppState,
    storage: SessionStorage | None = None,
) -> None:
    uid = message.from_user.id
    if not check_limit(uid, settings, state):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    doc = message.document
    if doc.file_size > 1_000_000:
        await message.answer("Файл слишком большой (макс 1MB).")
        return

    waiting = await message.answer("📄 Читаю файл...")

    file = await message.bot.get_file(doc.file_id)
    tmp_path = tempfile.mktemp(suffix=f"_{doc.file_name}")
    await message.bot.download_file(file.file_path, tmp_path)

    try:
        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        await waiting.edit_text(f"Не удалось прочитать файл: {e}")
        return
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    caption = message.caption or "Проанализируй этот файл"
    prompt = (
        f"Пользователь отправил файл `{doc.file_name}`:\n\n"
        f"```\n{content[:10000]}\n```\n\n"
        f"Задача: {caption}"
    )

    await waiting.edit_text("⏳ Claude думает...")

    response = await run_claude(prompt, uid, settings, state, storage=storage)
    await send_long(message, response.text, settings.max_message_len)
    if response.files:
        await send_files(message, response.files)

    await safe_delete(waiting)
