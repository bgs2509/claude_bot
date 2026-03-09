"""Отправка AI-ответов в Telegram."""

import os
import tempfile

from aiogram import types
from aiogram.types import FSInputFile

from claude_bot.services.format_telegram import markdown_to_telegram_html


async def _send_html_or_plain(message: types.Message, text: str) -> None:
    """Отправить сообщение как HTML, при ошибке отдать plain text."""

    formatted = markdown_to_telegram_html(text)
    try:
        await message.answer(formatted, parse_mode="HTML")
    except Exception:
        await message.answer(text)


async def send_long(message: types.Message, text: str, max_len: int = 4000) -> None:
    """Отправить ответ. Если он длиннее лимита, приложить полный текст файлом."""

    if not text.strip():
        text = "(пустой ответ)"

    if len(text) <= max_len:
        await _send_html_or_plain(message, text)
        return

    preview = text[:max_len]
    await _send_html_or_plain(message, preview)

    fd, md_path = tempfile.mkstemp(suffix=".md")
    os.close(fd)

    try:
        with open(md_path, "w", encoding="utf-8") as response_file:
            response_file.write(text)
        document = FSInputFile(md_path, filename="response.md")
        await message.answer_document(document, caption="Полный ответ в файле")
    finally:
        try:
            os.unlink(md_path)
        except OSError:
            pass
