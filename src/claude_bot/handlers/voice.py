"""Обработка голосовых сообщений."""

import asyncio
import logging

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.errors import get_user_message
from claude_bot.middlewares.auth import check_rate_limit, track_usage
from claude_bot.services.speech import transcribe_voice
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

from . import call_claude_safe, download_file, send_voice_if_enabled

router = Router(name="voice")
log = logging.getLogger("claude-bot.voice")


@router.message(F.voice)
async def handle_voice(
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

    log.info("Голосовое сообщение")
    waiting = await message.answer("🎤 Транскрибирую...")

    ogg_path = await download_file(message.bot, message.voice.file_id, ".ogg")

    text = await transcribe_voice(ogg_path, settings, app_state)
    if not text:
        await waiting.edit_text(get_user_message("voice_not_recognized"))
        return

    await waiting.edit_text(f"🎤 Распознано: {text}\n\n⏳ Claude думает...")

    response = await call_claude_safe(
        message, waiting, text, uid, settings, app_state, storage,
    )
    if response:
        await send_voice_if_enabled(message, response.text, uid, settings, app_state)
