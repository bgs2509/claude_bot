"""Настройка логирования: JSON в файл с ротацией, текст в консоль, Sentry."""

import logging
from logging.handlers import RotatingFileHandler

from pythonjsonlogger import jsonlogger

from ai_steward.config import Settings
from ai_steward.context import request_id_var, user_id_var


class _ContextFilter(logging.Filter):
    """Добавляет request_id и user_id ко всем log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.request_id = request_id_var.get("---")  # type: ignore[attr-defined]
        record.user_id = user_id_var.get("---")  # type: ignore[attr-defined]
        return True


def setup_logging(settings: Settings) -> None:
    """Настроить логирование: JSON в файл + текст в консоль."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    ctx_filter = _ContextFilter()

    # Консольный хендлер — текстовый формат для разработки
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s [%(request_id)s uid:%(user_id)s]: %(message)s"
    ))
    console.addFilter(ctx_filter)
    root.addHandler(console)

    # JSON-хендлер — файл с ротацией
    settings.log_file.parent.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.INFO)
    json_fmt = jsonlogger.JsonFormatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={"asctime": "timestamp", "levelname": "level", "name": "logger"},
    )
    file_handler.setFormatter(json_fmt)
    file_handler.addFilter(ctx_filter)
    root.addHandler(file_handler)

    # Заглушить шумные библиотеки
    logging.getLogger("aiogram").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


def setup_sentry(settings: Settings) -> None:
    """Инициализировать Sentry если SENTRY_DSN задан."""
    if not settings.sentry_dsn:
        return
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        traces_sample_rate=0.05,
        send_default_pii=False,
        integrations=[
            LoggingIntegration(level=logging.ERROR, event_level=logging.ERROR),
        ],
    )
