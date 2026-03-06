```
  ___  _                 _         ____        _
 / __|| | __ _  _   _  __| |  ___  | __ )  ___ | |_
| |   | |/ _` || | | |/ _` | / _ \ |  _ \ / _ \| __|
| |___| | (_| || |_| | (_| ||  __/ | |_) | (_) | |_
 \____|_|\__,_| \__,_|\__,_| \___| |____/ \___/ \__|
```

# Claude Code Telegram Bot

**Твой личный AI-ассистент прямо в Telegram — пиши текстом, говори голосом, кидай фотки и документы.**

`Python 3.11+` · `aiogram 3` · `Claude Code CLI` · `MCP серверы`

---

## 🤖 Что умеет

- **💬 Текст** — отправляешь сообщение → получаешь ответ от Claude Code
- **🎤 Голос** — говоришь голосом → бот распознаёт (faster-whisper) → отвечает текстом и голосом (edge-tts)
- **📷 Фото** — кидаешь скриншот или фотку → OCR (tesseract) → Claude анализирует
- **📄 Документы** — отправляешь файл → бот читает содержимое → Claude обрабатывает
- **👥 Мультипользователь** — роли admin/user/readonly, дневные лимиты, изоляция проектов
- **📂 Мульти-проект** — переключайся между проектами прямо в чате (`/project`)
- **🔌 MCP серверы** — GitHub, Playwright, Brave Search, PostgreSQL, SQLite и ещё 6 штук
- **🧠 Сессии** — Claude помнит контекст разговора в рамках сессии
- **📊 Мониторинг** — healthcheck, бэкапы, автоматические алерты в Telegram

---

## ⚡ Быстрый старт

```bash
git clone <repo-url> claude_bot
cd claude_bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполни TELEGRAM_BOT_TOKEN и PROJECTS_DIR в .env
python bot.py
```

> Для голоса и OCR нужны `ffmpeg` и `tesseract` — см. раздел «Требования» ниже.

---

## 📋 Требования

| Компонент | Зачем | Установка (Ubuntu) |
|-----------|-------|--------------------|
| **Python 3.11+** | Сам бот | `sudo apt install python3 python3-venv` |
| **Node.js 22+** | Claude Code CLI и MCP серверы | `curl -fsSL https://deb.nodesource.com/setup_22.x \| sudo bash -` |
| **Claude Code CLI** | Мозги бота | `npm install -g @anthropic-ai/claude-code` |
| **ffmpeg** | Конвертация голосовых OGG → WAV | `sudo apt install ffmpeg` |
| **tesseract-ocr** | Распознавание текста на фото | `sudo apt install tesseract-ocr tesseract-ocr-rus` |

---

## 🛠 Установка

### Локально (для разработки)

```bash
# Автоматически — скрипт установит все зависимости
bash scripts/setup-local.sh

# Или вручную
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Заполнить .env → запустить: python bot.py
```

### На VPS (production)

```bash
# 1. Настройка сервера (от root)
bash scripts/setup-server.sh

# 2. Безопасность: SSH, firewall, fail2ban
bash scripts/setup-security.sh

# 3. Авторизация Claude Code
su - claude
claude auth login

# 4. Запуск через systemd
sudo systemctl enable claude-bot
sudo systemctl start claude-bot
```

> 📖 Полная пошаговая инструкция с выбором VPS, hardening и troubleshooting — в **[GUIDE.md](GUIDE.md)**

---

## ⚙️ Конфигурация

Все настройки через переменные окружения в `.env` (скопируй из [.env.example](.env.example)):

| Переменная | Обяз. | Описание | По умолчанию |
|------------|:-----:|----------|:------------:|
| `TELEGRAM_BOT_TOKEN` | ✅ | Токен от [@BotFather](https://t.me/BotFather) | — |
| `PROJECTS_DIR` | ✅ | Директория с проектами | `/home/claude/projects` |
| `USERS` | — | JSON с пользователями и ролями | `{}` (доступ всем) |
| `WHISPER_MODEL` | — | Модель STT: `tiny`, `base`, `small` | `base` |
| `TTS_VOICE` | — | Голос TTS | `ru-RU-DmitryNeural` |
| `CLAUDE_TIMEOUT` | — | Таймаут ответа Claude (сек) | `600` |

### Настройка пользователей

```json
{
  "123456789": {
    "role": "admin",
    "limit": 0,
    "name": "Владелец"
  },
  "987654321": {
    "role": "user",
    "limit": 50,
    "name": "Коллега"
  }
}
```

| Роль | Что может |
|------|-----------|
| `admin` | Всё + `/stats` + без лимитов |
| `user` | Текст, голос, фото, документы (с лимитом) |
| `readonly` | Только чтение ответов |

> Если `USERS={}` — бот доступен всем (удобно для разработки).

---

## 💬 Команды бота

| Команда | Описание | Кто может |
|---------|----------|-----------|
| `/start` | Приветствие и информация | Все |
| `/new` | Новая сессия (сброс контекста) | user, admin |
| `/cancel` | Отменить текущий запрос | user, admin |
| `/session` | Показать ID текущей сессии | user, admin |
| `/project` | Переключить проект | user, admin |
| `/voice` | Включить/выключить голосовые ответы | user, admin |
| `/stats` | Статистика использования | admin |

---

## 🏗 Архитектура

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Telegram   │────▶│    bot.py    │────▶│  Claude Code CLI │
│  (сообщения) │◀────│   (aiogram)  │◀────│   (subprocess)   │
└──────────────┘     └──────┬───────┘     └────────┬─────────┘
                            │                      │
                    ┌───────┴───────┐       ┌──────┴──────┐
                    │  Обработчики  │       │ MCP серверы │
                    ├───────────────┤       ├─────────────┤
                    │ 🎤 STT/TTS    │       │ GitHub      │
                    │ 📷 OCR        │       │ Playwright  │
                    │ 📄 Документы  │       │ Brave Search│
                    │ 📝 Текст      │       │ PostgreSQL  │
                    └───────────────┘       │ SQLite      │
                                            │ Fetch       │
                                            │ Memory      │
                                            │ ...         │
                                            └─────────────┘
```

### Структура проекта

```
claude_bot/
├── bot.py                  # Основной код бота (все обработчики)
├── requirements.txt        # Python зависимости
├── .env.example            # Шаблон переменных окружения
├── claude-bot.service      # Systemd unit для автозапуска
├── GUIDE.md                # Полное руководство (1000+ строк)
├── configs/
│   └── claude-settings.json    # Конфигурация MCP серверов
└── scripts/
    ├── setup-local.sh      # Установка локально
    ├── setup-server.sh     # Настройка VPS
    ├── setup-security.sh   # Безопасность сервера
    ├── backup.sh           # Автоматический бэкап
    ├── update.sh           # Обновление компонентов
    └── healthcheck.sh      # Мониторинг и алерты
```

---

## 🔧 Скрипты обслуживания

| Скрипт | Что делает | Запуск |
|--------|-----------|--------|
| `setup-local.sh` | Установка ffmpeg, tesseract, venv, зависимостей | `bash scripts/setup-local.sh` |
| `setup-server.sh` | Первоначальная настройка VPS: Node.js, Python, swap | `sudo bash scripts/setup-server.sh` |
| `setup-security.sh` | SSH hardening, UFW firewall, fail2ban | `sudo bash scripts/setup-security.sh` |
| `backup.sh` | Бэкап бота, проектов и конфигов | Cron: `0 3 * * *` |
| `update.sh` | Обновление Claude Code, MCP, Python deps | `bash scripts/update.sh` |
| `healthcheck.sh` | Проверка: бот жив, диск, RAM + алерты в Telegram | Cron: `*/5 * * * *` |

### Пример cron для production

```cron
# Бэкап каждый день в 3:00
0 3 * * * /home/claude/claude-bot/scripts/backup.sh

# Проверка здоровья каждые 5 минут
*/5 * * * * /home/claude/claude-bot/scripts/healthcheck.sh

# Обновление раз в неделю (понедельник, 4:00)
0 4 * * 1 /home/claude/claude-bot/scripts/update.sh
```

---

## 📖 Полная документация

Всё, что не вошло в README — подробные инструкции, troubleshooting, выбор VPS, настройка MCP серверов, восстановление из бэкапа — в **[GUIDE.md](GUIDE.md)**.
