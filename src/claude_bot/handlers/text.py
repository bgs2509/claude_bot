"""Обработка текстовых сообщений."""

import asyncio

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_rate_limit, track_usage
from claude_bot.services.claude import run_claude, send_long
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

from . import safe_delete, send_files, send_voice_if_enabled

router = Router(name="text")


@router.message(F.text)
async def handle_text(
    message: Message,
    settings: Settings,
    state: AppState,
    storage: SessionStorage | None = None,
) -> None:
    uid = message.from_user.id
    wait = check_rate_limit(uid, settings, state)
    if wait > 0:
        await asyncio.sleep(wait)
        # После ожидания — зарегистрировать запрос
        check_rate_limit(uid, settings, state)
    track_usage(uid, state)

    prompt = message.text
    if not prompt:
        return

    waiting = await message.answer("⏳ Claude думает...")

    response = await run_claude(prompt, uid, settings, state, storage=storage)
    await send_long(message, response.text, settings.max_message_len)
    if response.files:
        await send_files(message, response.files)

    await send_voice_if_enabled(message, response.text, uid, settings, state)
    await safe_delete(waiting)
