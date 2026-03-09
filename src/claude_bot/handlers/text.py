"""Обработка текстовых сообщений."""

import logging

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_limit
from claude_bot.services.claude import run_claude, send_long
from claude_bot.state import AppState

from . import safe_delete, send_files, send_voice_if_enabled

router = Router(name="text")
log = logging.getLogger("claude-bot")


@router.message(F.text)
async def handle_text(message: Message, settings: Settings, state: AppState) -> None:
    uid = message.from_user.id
    if not check_limit(uid, settings, state):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    prompt = message.text
    if not prompt:
        return

    log.info("[uid=%s] prompt: %.80s", uid, prompt)
    waiting = await message.answer("⏳ Claude думает...")

    log.info("[uid=%s] calling run_claude...", uid)
    response = await run_claude(prompt, uid, settings, state)
    log.info("[uid=%s] run_claude done, text len=%d", uid, len(response.text))
    await send_long(message, response.text, settings.max_message_len)
    if response.files:
        await send_files(message, response.files)

    await send_voice_if_enabled(message, response.text, uid, settings, state)
    await safe_delete(waiting)
