"""Обработка текстовых сообщений."""

import logging

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_limit
from claude_bot.services.ai.manager import AIManager
from claude_bot.services.telegram_output import send_long
from claude_bot.state import AppState

from . import safe_delete, send_files, send_voice_if_enabled

router = Router(name="text")
log = logging.getLogger("claude-bot")


@router.message(F.text)
async def handle_text(
    message: Message,
    settings: Settings,
    state: AppState,
    role: str,
    ai_manager: AIManager,
) -> None:
    uid = message.from_user.id
    if not check_limit(uid, settings, state):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    prompt = message.text
    if not prompt:
        return

    provider_name = ai_manager.get_current_provider_name(uid, settings, state)
    log.info("[uid=%s] prompt: %.80s", uid, prompt)
    waiting = await message.answer(f"⏳ {provider_name} обрабатывает запрос...")

    log.info("[uid=%s] calling provider=%s", uid, provider_name)
    response = await ai_manager.run(prompt, uid, role, settings, state)
    log.info("[uid=%s] provider=%s done, text len=%d", uid, provider_name, len(response.text))
    await send_long(message, response.text, settings.max_message_len)
    if response.files:
        await send_files(message, response.files)

    await send_voice_if_enabled(message, response.text, uid, settings, state)
    await safe_delete(waiting)
