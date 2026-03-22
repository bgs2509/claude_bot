"""Обработка документов — сохранение в проект + передача Claude."""

import asyncio
import logging
import os

from aiogram import F, Router
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from ai_steward.config import Settings
from ai_steward.errors import get_user_message
from ai_steward.middlewares.auth import check_rate_limit, track_usage
from ai_steward.services.claude import get_project_dir
from ai_steward.services.storage import SessionStorage
from ai_steward.services.upload import (
    build_file_prompt,
    check_collision,
    is_binary_file,
    save_uploaded_file,
)
from ai_steward.state import AppState, PendingUpload

from . import call_claude_safe, download_file

router = Router(name="document")
log = logging.getLogger("ai-steward.document")


@router.message(F.document)
async def handle_document(
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

    doc = message.document
    if doc.file_size > settings.max_upload_size:
        limit_mb = settings.max_upload_size // 1_048_576
        await message.answer(project_tag + get_user_message("file_too_large", limit_mb=limit_mb), parse_mode="HTML")
        return

    try:
        project_dir = get_project_dir(settings, storage, uid)
    except ValueError:
        await message.answer(project_tag + get_user_message("no_active_project"), parse_mode="HTML")
        return

    filename = doc.file_name or "unnamed_file"
    binary = is_binary_file(filename, doc.mime_type)
    caption = message.caption or "Проанализируй этот файл"

    log.info("Документ: %s (%d bytes, binary=%s)", filename, doc.file_size, binary)
    waiting = await message.answer(project_tag + "📄 Сохраняю файл в проект...", parse_mode="HTML")
    tmp_path = await download_file(message.bot, doc.file_id, f"_{filename}")

    # Очистить предыдущий pending если есть
    old = app_state.pending_uploads.pop(uid, None)
    if old:
        _cleanup_tmp(old.tmp_path)

    if check_collision(project_dir, filename):
        app_state.pending_uploads[uid] = PendingUpload(
            tmp_path=tmp_path,
            target_dir=str(project_dir),
            filename=filename,
            is_binary=binary,
            caption=caption,
            chat_id=message.chat.id,
        )
        await waiting.edit_text(
            project_tag + get_user_message("file_collision", filename=filename),
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(
                    text="Перезаписать", callback_data="upload:overwrite",
                ),
                InlineKeyboardButton(
                    text="Добавить дату", callback_data="upload:suffix",
                ),
            ]]),
        )
        return

    saved = save_uploaded_file(tmp_path, project_dir, filename)
    prompt = build_file_prompt(filename, saved, binary, caption)
    await waiting.edit_text(project_tag + "⏳ Claude думает...", parse_mode="HTML")
    await call_claude_safe(message, waiting, prompt, uid, settings, app_state, storage, project_tag=project_tag)


def _cleanup_tmp(path: str) -> None:
    try:
        os.unlink(path)
    except OSError:
        pass
