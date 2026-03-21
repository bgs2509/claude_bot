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

Бот настраивается через `.env`, `data/users.json`, конфиги MCP-серверов и системные промпты — всё прозрачно для разработчика.

---

## Что умеет

- **Текст** — вопросы, задачи, работа с кодом через Claude Code
- **Голос** — распознавание речи (faster-whisper) → Claude → озвучка ответа (edge-tts)
- **Фото** — OCR (tesseract) → Claude анализирует
- **Документы** — чтение файлов и обработка содержимого
- **Проекты и сессии** — управление контекстом через inline-меню (`/menu`): именованные проекты и сессии
- **MCP серверы** — GitHub, Playwright, Brave Search, PostgreSQL и другие
- **Мультипользователь** — роли admin/user/readonly, дневные лимиты, конфигурация в `data/users.json`

---

## Быстрый старт

```bash
git clone <repo-url> claude_bot
cd claude_bot
cp .env.example .env
cp users.json.example data/users.json
# Заполни TELEGRAM_BOT_TOKEN в .env
# Настрой пользователей в data/users.json
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
| `/menu` | Проекты и сессии (главное меню с кнопками) |
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
├── users.json.example         # Шаблон конфигурации пользователей
├── claude-bot.service         # Systemd unit для автозапуска
├── src/claude_bot/
│   ├── __main__.py            # Точка входа
│   ├── bot.py                 # Фабрики create_bot / create_dispatcher
│   ├── config.py              # Settings (pydantic-settings)
│   ├── state.py               # AppState (in-memory состояние)
│   ├── keyboards.py           # Inline-клавиатуры (главное меню, пагинация)
│   ├── handlers/
│   │   ├── commands.py        # Команды бота
│   │   ├── menu.py            # /menu, проекты, сессии (inline callback)
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
│       ├── ocr.py             # ocr_image
│       └── storage.py         # SessionStorage (проекты, сессии, пользователи)
├── CHANGELOG.md              # Журнал изменений
├── CLAUDE.md                 # Инструкции для Claude Code
├── docs/
│   ├── adr/                  # Архитектурные решения (ADR)
│   │   ├── README.md         # Индекс и шаблон
│   │   ├── 001-aiogram.md
│   │   ├── 002-claude-code-cli.md
│   │   ├── 003-faster-whisper.md
│   │   ├── 004-edge-tts.md
│   │   ├── 005-tesseract.md
│   │   ├── 006-modular-architecture.md
│   │   ├── 007-pydantic-settings.md
│   │   └── 008-uv.md
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

- **[CHANGELOG.md](CHANGELOG.md)** — журнал изменений (v1.0.0 → v2.0.0)
- **[docs/adr/](docs/adr/)** — архитектурные решения (ADR)
- **[docs/USAGE.md](docs/USAGE.md)** — руководство пользователя: команды, типы ввода, модели, примеры, FAQ
- **[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)** — развёртывание: VPS, hardening, Claude Code, systemd, бэкапы, MCP серверы, troubleshooting
