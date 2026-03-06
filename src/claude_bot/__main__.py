"""Точка входа: python -m claude_bot / uv run claude-bot."""

import asyncio
import logging

from claude_bot.bot import create_bot, create_dispatcher
from claude_bot.config import Settings
from claude_bot.state import AppState

log = logging.getLogger("claude-bot")


async def _run() -> None:
    settings = Settings()
    state = AppState()

    log.info("Claude Code Telegram Bot запущен")
    log.info("Проекты: %s", settings.projects_dir)
    log.info("Пользователей: %s", len(settings.users) or "без ограничений")
    log.info("Whisper модель: %s (device=%s)", settings.whisper_model, settings.whisper_device)
    log.info("TTS голос: %s", settings.tts_voice)

    bot = create_bot(settings)
    dp = create_dispatcher(settings, state)
    await dp.start_polling(bot)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(_run())


if __name__ == "__main__":
    main()
