"""Обработка текстовых сообщений."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from ai_steward.config import Settings
from ai_steward.context import obs_status_var
from ai_steward.middlewares.auth import check_rate_limit, track_usage
from ai_steward.services.storage import SessionStorage
from ai_steward.state import AppState

from . import call_claude_safe, send_voice_if_enabled

router = Router(name="text")
log = logging.getLogger("ai-steward.text")


@router.message(F.text)
async def handle_text(
    message: Message,
    settings: Settings,
    app_state: AppState,
    storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    uid = message.from_user.id
    wait = check_rate_limit(uid, settings, app_state)
    if wait > 0:
        obs_status_var.set("rate_limited")
        await asyncio.sleep(wait)
        # После ожидания — зарегистрировать запрос
        check_rate_limit(uid, settings, app_state)
    track_usage(uid, app_state)

    prompt = message.text
    if not prompt:
        return

    log.info("Текст, len=%d", len(prompt))
    waiting = await message.answer(project_tag + "⏳ Claude думает...", parse_mode="HTML")

    response = await call_claude_safe(
        message, waiting, prompt, uid, settings, app_state, storage,
        project_tag=project_tag,
    )
    if response:
        await send_voice_if_enabled(message, response.text, uid, settings, app_state)
