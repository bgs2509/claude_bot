# Changelog

Все значимые изменения в проекте документируются в этом файле.

Формат основан на [Keep a Changelog](https://keepachangelog.com/ru/1.1.0/),
версионирование — [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- JSON-логи с ротацией в `data/bot.log` (5x10MB)
- ObservabilityMiddleware: тип события, latency, статус каждого запроса
- SQLite-аналитика в `data/analytics.db` с автоочисткой >90 дней
- Sentry интеграция (опционально через `SENTRY_DSN`)
- Логирование всех команд, callback-навигации, OCR, TTS, rate-limit
- Rate-limit 2 запроса в минуту для роли `user` с молчаливым ожиданием
- Поле `model` в конфиге пользователя (`.env`) для задания модели каждому юзеру
- Загрузка файлов и фото в директорию проекта (сохраняются для Claude CLI)
- При коллизии имён: inline-кнопки «Перезаписать» / «Добавить дату»
- Бинарные файлы: Claude получает путь к файлу
- Текстовые файлы: содержимое передаётся в промпт + файл сохраняется
- Настройка `MAX_UPLOAD_SIZE` (по умолчанию 20MB)
- Reply-клавиатура для быстрого переключения проекта (кнопки с названиями проектов)
- Reply-клавиатура привязана к `/start`
- Иерархия исключений: `AppError` → `DomainError`, `InfrastructureError` с каталогом user-friendly сообщений (`errors.py`)
- Публичный метод `storage.get_active_session_name()` (Law of Demeter)
- Make-target `logs-vps` для просмотра логов systemd-сервиса

### Changed

- Имена логгеров сервисов: `claude-bot` -> `claude-bot.{service}`
- Настройки: добавлены `LOG_FILE`, `SENTRY_DSN`, `ANALYTICS_DB` и др.
- Директория проектов теперь per-user: обязательное поле `projects_dir` в конфиге каждого пользователя (`USERS`)
- Удалён глобальный `PROJECTS_DIR`, добавлен `SESSIONS_FILE` для пути к файлу сессий
- Лимит размера файла вынесен в настройку `MAX_UPLOAD_SIZE` (было: 1MB в коде, теперь: 20MB)
- Фото сохраняются в проект как `photo_YYYYMMDD_HHMMSS.jpg` (было: OCR + удаление)
- Файлы в `_output/` больше не удаляются между запросами (накапливаются в проекте)
- Выходные файлы Claude именуются с датой и описанием (YYYYMMDD_HHMMSS_описание.ext)
- Команда `/model` доступна только для admin
- Модель юзера с ролью `user` фиксируется из конфига и не может быть изменена
- Дневной лимит сообщений заменён на поминутный rate-limit
- `/usage` показывает только счётчик без лимита
- Google-style docstrings в публичных функциях и классах
- Structured logging: именованные параметры (uid, username, reason) в auth, storage, __main__
- SRP: `send_long()` перенесён из `services/claude.py` в `handlers/__init__.py`
- `ErrorMiddleware` различает `DomainError` (warning) и `AppError` (error, со stack trace)
- systemd-сервис обновлён для текущего окружения

### Fixed

- Reply-клавиатура не отображалась при отсутствии проектов у пользователя

## [2.0.0] - 2026-03-06

Проекты и сессии — полное управление рабочими пространствами через Telegram.

### Added

- Главное меню `/menu` с inline-клавиатурой и пагинацией
- Навигация по проектам и сессиям (выбор, создание, переключение)
- `SessionStorage` — персистентное JSON-хранилище проектов и сессий
- FSM для создания проектов (валидация имени, создание директории)
- `keyboards.py` — модуль inline-клавиатур с пагинацией
- Автоименование сессий через парсинг `[TITLE:]` из ответа Claude
- Привязка `run_claude()` к директории активного проекта (`cwd`)

### Changed

- README переписан с фокусом на разработчиков (архитектура, структура, запуск)

## [1.1.0] - 2026-03-06

Модульная архитектура — разбивка монолита на 12+ модулей.

### Added

- Модульная архитектура `src/claude_bot/` (handlers, services, middlewares)
- `pyproject.toml` с метаданными и зависимостями
- `pydantic-settings` для валидации конфигурации через `.env`
- `AuthMiddleware` — авторизация, роли, дневные лимиты
- `ClaudeResponse` dataclass для структурированного ответа от CLI
- `format_telegram.py` — конвертация Markdown в Telegram HTML
- `Makefile` с командами `install`, `run`, `dev`, `lint`
- Команды: `/help`, `/model`, `/status`, `/usage`, `/stats`, `/voice`, `/cancel`

### Changed

- Монолит `bot.py` разбит на модули: handlers, services, middlewares
- `requirements.txt` заменён на `pyproject.toml` + `uv.lock`

### Removed

- Старые команды `/project` и `/session` (заменены на `/menu`)
- `requirements.txt` (заменён на `pyproject.toml`)

### Fixed

- Дневной счётчик сообщений сбрасывается корректно при смене даты

## [1.0.0] - 2026-03-06

Начальная реализация — Telegram-бот с доступом к Claude Code CLI.

### Added

- Telegram-бот на aiogram 3.15 с long polling
- Обработка текстовых сообщений через Claude Code CLI
- Голосовые сообщения: STT (faster-whisper) → Claude → TTS (edge-tts)
- Распознавание фото: OCR (tesseract) → Claude
- Обработка текстовых документов
- Мультипользовательский доступ с ролями (admin, user, readonly)
- Сессии Claude (продолжение диалога через `--resume`)
- Поддержка MCP-серверов через Claude Code CLI
- systemd unit для автозапуска
- Скрипты деплоя: `setup-local.sh`, `setup-security.sh`, `backup.sh`, `healthcheck.sh`

### Fixed

- Транскрибация голоса: корректная обработка пустых сегментов
- Whisper CPU fallback при отсутствии CUDA
