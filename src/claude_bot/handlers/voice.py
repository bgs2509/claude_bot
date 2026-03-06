"""Обработка голосовых сообщений."""

from aiogram import F, Router
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.middlewares.auth import check_limit
from claude_bot.services.claude import run_claude, send_long
from claude_bot.services.speech import transcribe_voice
from claude_bot.state import AppState

from . import download_file, safe_delete, send_voice_if_enabled

router = Router(name="voice")


@router.message(F.voice)
async def handle_voice(message: Message, settings: Settings, state: AppState) -> None:
    uid = message.from_user.id
    if not check_limit(uid, settings, state):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    waiting = await message.answer("🎤 Транскрибирую...")

    ogg_path = await download_file(message.bot, message.voice.file_id, ".ogg")

    text = await transcribe_voice(ogg_path, settings, state)
    if not text:
        await waiting.edit_text("Не удалось распознать голос. Отправь текстом.")
        return

    await waiting.edit_text(f"🎤 Распознано: {text}\n\n⏳ Claude думает...")

    result = await run_claude(text, uid, settings, state)
    await send_long(message, result, settings.max_message_len)

    await send_voice_if_enabled(message, result, uid, settings, state)
    await safe_delete(waiting)
