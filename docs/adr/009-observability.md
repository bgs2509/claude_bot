# ADR-009: Observability-стек (JSON-логи + SQLite + Sentry)

**Статус:** Принято
**Дата:** 2026-03-09

## Контекст

Бот имел базовое текстовое логирование с request_id/user_id, но половина компонентов не логировала ничего (commands, menu, OCR, TTS). Latency не измерялась, результат обработки не фиксировался. Текстовые логи не парсились автоматически, ротация отсутствовала. Ошибки обнаруживались только при ручном просмотре логов.

## Решение

- **JSON-логи**: `python-json-logger` + `RotatingFileHandler` (5×10MB). NDJSON в файл, текст в консоль. Поля: timestamp, level, logger, message, request_id, user_id + extra.
- **ObservabilityMiddleware**: автоматическое определение типа события, измерение latency, чтение статуса из contextvars. Одна финальная запись на запрос.
- **EventLogger (SQLite)**: `aiosqlite`, WAL mode, таблица events, автоочистка >90 дней. Fire-and-forget запись из middleware.
- **Sentry**: `sentry-sdk` с `LoggingIntegration`. Опционально через `SENTRY_DSN`. При пустом DSN — не инициализируется.
- **Contextvars**: `obs_status_var` и `obs_output_var` для передачи статуса из хендлеров в middleware без изменения сигнатур.

## Альтернативы

- **structlog** — избыточен для текущего масштаба, python-json-logger проще и легче.
- **PostgreSQL для аналитики** — overkill для ~20 пользователей, SQLite достаточно.
- **Prometheus + Grafana + Loki** — infrastructure overhead непропорционален масштабу проекта.
