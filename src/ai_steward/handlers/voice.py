"""Обработка голосовых сообщений."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from ai_steward.config import Settings
from ai_steward.context import obs_status_var
from ai_steward.errors import get_user_message
from ai_steward.middlewares.auth import check_rate_limit, track_usage
from ai_steward.services.speech import transcribe_voice
from ai_steward.services.storage import SessionStorage
from ai_steward.state import AppState

from . import call_claude_safe, download_file, send_voice_if_enabled

router = Router(name="voice")
log = logging.getLogger("ai-steward.voice")


@router.message(F.voice)
async def handle_voice(
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
        check_rate_limit(uid, settings, app_state)
    track_usage(uid, app_state)

    log.info("Голосовое сообщение")
    waiting = await message.answer(project_tag + "🎤 Транскрибирую...", parse_mode="HTML")

    ogg_path = await download_file(message.bot, message.voice.file_id, ".ogg")

    text = await transcribe_voice(ogg_path, settings, app_state)
    if not text:
        await waiting.edit_text(project_tag + get_user_message("voice_not_recognized"), parse_mode="HTML")
        return

    await waiting.edit_text(project_tag + f"🎤 Распознано: {text}\n\n⏳ Claude думает...", parse_mode="HTML")

    response = await call_claude_safe(
        message, waiting, text, uid, settings, app_state, storage,
        project_tag=project_tag,
    )
    if response:
        await send_voice_if_enabled(message, response.text, uid, settings, app_state)
