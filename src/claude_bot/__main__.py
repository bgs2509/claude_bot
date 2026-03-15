"""Точка входа: python -m claude_bot / uv run claude-bot."""

import asyncio
import logging
import sys

from claude_bot import __version__
from claude_bot.bot import create_bot, create_dispatcher
from claude_bot.config import Settings
from claude_bot.logging_setup import setup_logging, setup_sentry
from claude_bot.services.analytics import EventLogger
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

log = logging.getLogger("claude-bot")


async def _run(settings: Settings) -> None:
    # Инициализировать EventLogger (бот работает и без него)
    event_logger: EventLogger | None = EventLogger(settings)
    try:
        await event_logger.init()
    except Exception as e:
        log.warning("EventLogger не инициализирован: %s", e)
        event_logger = None

    state = AppState()
    storage = SessionStorage(settings.sessions_file)

    log.info(
        "Startup: service=claude-bot version=%s python=%s users=%d",
        __version__, sys.version.split()[0], len(settings.users),
    )
    for uid_str, cfg in settings.users.items():
        log.info("  %s (%s): %s", cfg.get("name", uid_str), uid_str, cfg["projects_dir"])
    log.info("Whisper модель: %s (device=%s)", settings.whisper_model, settings.whisper_device)
    log.info("TTS голос: %s", settings.tts_voice)

    bot = create_bot(settings)

    # Установить команды бота в меню Telegram
    try:
        from aiogram.types import BotCommand
        await bot.set_my_commands([
            BotCommand(command="status", description="Проекты, сессии, настройки"),
            BotCommand(command="new", description="Новая сессия"),
            BotCommand(command="model", description="Сменить модель"),
            BotCommand(command="voice", description="Вкл/выкл голосовые ответы"),
            BotCommand(command="help", description="Справка"),
            BotCommand(command="cancel", description="Отменить запрос"),
        ])
    except Exception as e:
        log.warning("Не удалось установить команды бота: %s", e)

    dp = create_dispatcher(settings, state, storage, event_logger=event_logger)
    try:
        await dp.start_polling(bot)
    finally:
        if event_logger:
            await event_logger.close()


def main() -> None:
    settings = Settings()
    setup_logging(settings)
    setup_sentry(settings)
    asyncio.run(_run(settings))


if __name__ == "__main__":
    main()
