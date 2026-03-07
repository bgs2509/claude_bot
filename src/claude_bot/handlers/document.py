"""Обработка документов (текстовые файлы)."""

import asyncio
import logging
import os
import tempfile

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.errors import get_user_message
from claude_bot.middlewares.auth import check_rate_limit, track_usage
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

from . import call_claude_safe

router = Router(name="document")
log = logging.getLogger("claude-bot.document")


@router.message(F.document)
async def handle_document(
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

    doc = message.document
    if doc.file_size > 1_000_000:
        await message.answer(get_user_message("file_too_large"))
        return

    log.info("Документ: %s (%d bytes)", doc.file_name, doc.file_size)
    waiting = await message.answer("📄 Читаю файл...")

    file = await message.bot.get_file(doc.file_id)
    tmp_path = tempfile.mktemp(suffix=f"_{doc.file_name}")
    await message.bot.download_file(file.file_path, tmp_path)

    try:
        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read().replace("\x00", "")
    except Exception:
        log.error("Ошибка чтения файла %s", doc.file_name, exc_info=True)
        await waiting.edit_text(get_user_message("file_read_error"))
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

    await call_claude_safe(
        message, waiting, prompt, uid, settings, app_state, storage,
    )
