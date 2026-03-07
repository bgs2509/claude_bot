"""Точка входа: python -m claude_bot / uv run claude-bot."""

import asyncio
import logging

from claude_bot.bot import create_bot, create_dispatcher
from claude_bot.config import Settings
from claude_bot.context import request_id_var, user_id_var
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

log = logging.getLogger("claude-bot")


class _ContextFilter(logging.Filter):
    """Добавляет request_id и user_id ко всем log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("---")  # type: ignore[attr-defined]
        record.user_id = user_id_var.get("---")  # type: ignore[attr-defined]
        return True


async def _run() -> None:
    settings = Settings()
    state = AppState()
    storage = SessionStorage(settings.sessions_file)

    log.info("Claude Code Telegram Bot запущен")
    log.info("Пользователей: %s", len(settings.users) or "без ограничений")
    for uid_str, cfg in settings.users.items():
        log.info("  %s (%s): %s", cfg.get("name", uid_str), uid_str, cfg["projects_dir"])
    log.info("Whisper модель: %s (device=%s)", settings.whisper_model, settings.whisper_device)
    log.info("TTS голос: %s", settings.tts_voice)

    bot = create_bot(settings)
    dp = create_dispatcher(settings, state, storage)
    await dp.start_polling(bot)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s [%(request_id)s uid:%(user_id)s]: %(message)s",
    )
    # Фильтр на handler, чтобы record получал request_id/user_id ДО форматирования
    ctx_filter = _ContextFilter()
    for handler in logging.getLogger().handlers:
        handler.addFilter(ctx_filter)
    asyncio.run(_run())


if __name__ == "__main__":
    main()
