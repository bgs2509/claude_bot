"""Обработка голосовых сообщений."""

import asyncio

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_rate_limit, track_usage
from claude_bot.services.claude import run_claude, send_long
from claude_bot.services.speech import transcribe_voice
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

from . import download_file, safe_delete, send_files, send_voice_if_enabled

router = Router(name="voice")


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

    waiting = await message.answer("🎤 Транскрибирую...")

    ogg_path = await download_file(message.bot, message.voice.file_id, ".ogg")

    text = await transcribe_voice(ogg_path, settings, app_state)
    if not text:
        await waiting.edit_text("Не удалось распознать голос. Отправь текстом.")
        return

    await waiting.edit_text(f"🎤 Распознано: {text}\n\n⏳ Claude думает...")

    response = await run_claude(text, uid, settings, app_state, storage=storage)
    await send_long(message, response.text, settings.max_message_len)
    if response.files:
        await send_files(message, response.files)

    await send_voice_if_enabled(message, response.text, uid, settings, app_state)
    await safe_delete(waiting)
