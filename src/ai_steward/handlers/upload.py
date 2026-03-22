"""Обработчик callback-кнопок при коллизии имени файла."""

import logging
from pathlib import Path

from aiogram import F, Router
from aiogram.types import CallbackQuery

from ai_steward.config import Settings
from ai_steward.services.storage import SessionStorage
from ai_steward.services.upload import build_file_prompt, save_uploaded_file
from ai_steward.state import AppState

from . import call_claude_safe

router = Router(name="upload")
log = logging.getLogger("ai-steward.handlers.upload")


@router.callback_query(F.data == "upload:overwrite")
async def cb_overwrite(
    callback: CallbackQuery,
    settings: Settings,
    app_state: AppState,
    storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    await _resolve(callback, settings, app_state, storage, overwrite=True, project_tag=project_tag)


@router.callback_query(F.data == "upload:suffix")
async def cb_suffix(
    callback: CallbackQuery,
    settings: Settings,
    app_state: AppState,
    storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    await _resolve(callback, settings, app_state, storage, overwrite=False, project_tag=project_tag)


async def _resolve(
    callback: CallbackQuery,
    settings: Settings,
    app_state: AppState,
    storage: SessionStorage | None,
    *,
    overwrite: bool,
    project_tag: str = "",
) -> None:
    uid = callback.from_user.id
    pending = app_state.pending_uploads.pop(uid, None)
    if not pending:
        await callback.answer(
            "Загрузка устарела. Отправьте файл заново.", show_alert=True,
        )
        return

    await callback.answer()
    project_dir = Path(pending.target_dir)
    saved = save_uploaded_file(
        pending.tmp_path, project_dir, pending.filename, overwrite=overwrite,
    )
    prompt = build_file_prompt(
        saved.name, saved, pending.is_binary, pending.caption,
        ocr_text=pending.ocr_text,
    )

    await callback.message.edit_text(project_tag + "⏳ Claude думает...", parse_mode="HTML")
    await call_claude_safe(
        callback.message, callback.message, prompt, uid,
        settings, app_state, storage, project_tag=project_tag,
    )
