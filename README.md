# Claude Code Telegram Bot

Telegram-обёртка над Claude Code CLI — превращает Смартфон в терминал с ИИ.

**Для кого:** разработчики, которые хотят дать Claude Code доступ к своему серверу через Telegram — без SSH, без IDE, с телефона.

**Сценарии использования:**

- 💻 **Вайбкодинг на ходу** — телефон + Telegram = всё что нужно
    - 🚂 Фикснуть баг из поезда
    - 🏖️ Сгенерить скрипт на пляже
    - ☕ Запустить ревью из очереди за кофе
    - 🖥️ Для больших проектов нужны IDE и терминал, но для быстрых правок хватает чата
- 🤖 **Личный ИИ-ассистент** — Claude Code под капотом + файловая система + MCP-серверы
    - 📄 Анализ документов и фото
    - 📁 Хранение и поиск файлов
    - 🔍 OCR, отчёты, голосовые команды
    - 🧠 Бот умеет всё, что умеет Claude
- 👨‍👩‍👧‍👦 **ИИ для всей семьи** — один бот, несколько пользователей с разными ролями
    - 📚 Дети делают уроки
    - 🍳 Жена хранит рецепты
    - 💰 Семья ведёт домашний бюджет
    - ✨ Сценарии ограничены только фантазией

Бот настраивается через `.env`, конфиги MCP-серверов и системные промпты — всё прозрачно для разработчика.

---

## Что умеет

- **Текст** — вопросы, задачи, работа с кодом через Claude Code
- **Голос** — распознавание речи (faster-whisper) → Claude → озвучка ответа (edge-tts)
- **Фото** — OCR (tesseract) → Claude анализирует
- **Документы** — чтение файлов и обработка содержимого
- **MCP серверы** — GitHub, Playwright, Brave Search, PostgreSQL и другие
- **Мультипользователь** — роли admin/user/readonly, дневные лимиты

---

## Быстрый старт

```bash
git clone <repo-url> claude_bot
cd claude_bot
cp .env.example .env
# Заполни TELEGRAM_BOT_TOKEN и PROJECTS_DIR в .env
make install
make run
```

---

## Требования

| Компонент | Зачем | Установка (Ubuntu) |
|-----------|-------|--------------------|
| **Python 3.11+** | Сам бот | `sudo apt install python3` |
| **uv** | Пакетный менеджер | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js 22+** | Claude Code CLI и MCP серверы | `curl -fsSL https://deb.nodesource.com/setup_22.x \| sudo bash -` |
| **Claude Code CLI** | Мозги бота | `npm install -g @anthropic-ai/claude-code` |
| **ffmpeg** | Конвертация голосовых OGG → WAV | `sudo apt install ffmpeg` |
| **tesseract-ocr** | Распознавание текста на фото | `sudo apt install tesseract-ocr tesseract-ocr-rus` |

---

## Команды бота

| Команда | Описание |
|---------|----------|
| `/help` | Справка и список команд |
| `/new` | Новая сессия (сброс контекста) |
| `/cancel` | Отменить текущий запрос |
| `/model` | Сменить модель (haiku / sonnet / opus) |
| `/voice` | Вкл/выкл голосовые ответы |
| `/status` | Текущее состояние |
| `/usage` | Статистика за сегодня |
| `/stats` | Статистика всех (admin) |

Подробнее — в [docs/USAGE.md](docs/USAGE.md).

---

## Структура проекта

```
claude_bot/
├── pyproject.toml             # Зависимости и метаданные
├── Makefile                   # make run, make install, make clean
├── .env.example               # Шаблон переменных окружения
├── claude-bot.service         # Systemd unit для автозапуска
├── src/claude_bot/
│   ├── __main__.py            # Точка входа
│   ├── bot.py                 # Фабрики create_bot / create_dispatcher
│   ├── config.py              # Settings (pydantic-settings)
│   ├── state.py               # AppState (in-memory состояние)
│   ├── handlers/
│   │   ├── commands.py        # Команды бота
│   │   ├── text.py            # Текстовые сообщения
│   │   ├── voice.py           # Голосовые сообщения
│   │   ├── photo.py           # Фотографии
│   │   └── document.py        # Документы
│   ├── middlewares/
│   │   └── auth.py            # Авторизация + check_limit
│   └── services/
│       ├── claude.py          # ClaudeResponse, run_claude, send_long
│       ├── format_telegram.py # Markdown → Telegram HTML
│       ├── speech.py          # transcribe_voice, synthesize_speech
│       └── ocr.py             # ocr_image
├── configs/
│   └── claude-settings.json   # Конфигурация MCP серверов
├── docs/
│   ├── USAGE.md               # Руководство пользователя
│   └── DEPLOYMENT.md          # Развёртывание и администрирование
└── scripts/
    ├── setup-local.sh         # Установка локально
    ├── setup-server.sh        # Настройка VPS
    ├── setup-security.sh      # Безопасность сервера
    ├── backup.sh              # Автоматический бэкап
    ├── update.sh              # Обновление компонентов
    └── healthcheck.sh         # Мониторинг и алерты
```

---

## Документация

- **[docs/USAGE.md](docs/USAGE.md)** — руководство пользователя: команды, типы ввода, модели, примеры, FAQ
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — развёртывание: VPS, hardening, Claude Code, systemd, бэкапы, MCP серверы, troubleshooting
