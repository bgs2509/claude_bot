# Claude Code Telegram Bot — Полное руководство по развёртыванию на VPS

> Универсальный AI-ассистент в Telegram: разработка, учёба, медиа, документация, аналитика.

---

## Содержание

1. [Обзор и архитектура](#1-обзор-и-архитектура)
2. [Требования к VPS](#2-требования-к-vps)
3. [Первоначальная настройка сервера](#3-первоначальная-настройка-сервера)
4. [Hardening безопасности](#4-hardening-безопасности)
5. [Установка Claude Code](#5-установка-claude-code)
6. [Код Telegram-бота](#6-код-telegram-бота)
7. [Голосовой режим (STT + TTS)](#7-голосовой-режим-stt--tts)
8. [Работа с фото и картинками](#8-работа-с-фото-и-картинками)
9. [Мульти-юзер режим](#9-мульти-юзер-режим)
10. [MCP серверы (бесплатные)](#10-mcp-серверы-бесплатные)
11. [Systemd и автозапуск](#11-systemd-и-автозапуск)
12. [Бэкапы и восстановление](#12-бэкапы-и-восстановление)
13. [Мониторинг и алерты](#13-мониторинг-и-алерты)
14. [Обновление и обслуживание](#14-обновление-и-обслуживание)
15. [Troubleshooting](#15-troubleshooting)
16. [Локальная машина vs VPS](#локальная-машина-vs-vps)
17. [Локальное развёртывание](#локальное-развёртывание)

---

## 1. Обзор и архитектура

### Что это

Telegram-бот, который проксирует сообщения в Claude Code CLI. Ты пишешь в Telegram с телефона — Claude Code выполняет команды на сервере и отвечает.

### Архитектура

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   Telegram   │────→│   Bot (Python)   │────→│  Claude Code    │
│   (телефон)  │←────│   aiogram 3.x    │←────│  CLI            │
└──────────────┘     └──────────────────┘     └────────┬────────┘
                                                       │
                              ┌─────────────────────────┤
                              │                         │
                     ┌────────▼───────┐      ┌──────────▼─────────┐
                     │  MCP серверы   │      │  Файловая система  │
                     │  (playwright,  │      │  проектов          │
                     │   github, ...) │      │                    │
                     └────────────────┘      └────────────────────┘
```

### Поток данных

1. Пользователь отправляет сообщение (текст/голос/фото) в Telegram
2. Бот получает сообщение через Telegram Bot API
3. Голос → транскрибируется в текст (faster-whisper)
4. Фото → описывается/OCR (tesseract)
5. Текст → передаётся в `claude -p` как промпт
6. Claude Code выполняет задачу (читает файлы, пишет код, вызывает MCP)
7. Результат → отправляется обратно в Telegram
8. Опционально: текст → озвучивается (edge-tts) → голосовое сообщение

---

## 2. Требования к VPS

### Минимальные (только текст)

| Параметр | Значение |
|----------|----------|
| CPU | 2 vCPU |
| RAM | 2 GB |
| Диск | 40 GB SSD |
| ОС | Ubuntu 24.04 LTS |
| Сеть | 1 Гбит/с |

### Рекомендуемые (текст + голос + браузер)

| Параметр | Значение |
|----------|----------|
| CPU | 2-4 vCPU |
| RAM | 4 GB |
| Диск | 80 GB SSD |
| ОС | Ubuntu 24.04 LTS |
| Сеть | 1 Гбит/с |

### Сравнение провайдеров (март 2026)

| Провайдер | Тариф | CPU | RAM | Диск | Цена |
|-----------|-------|-----|-----|------|------|
| **Hetzner** (рекомендуется) | CX22 | 2 vCPU | 4 GB | 40 GB | €4.35/мес |
| **Hetzner** | CX32 | 4 vCPU | 8 GB | 80 GB | €7.69/мес |
| **DigitalOcean** | Basic | 2 vCPU | 4 GB | 80 GB | $24/мес |
| **Timeweb** | Старт | 2 vCPU | 4 GB | 60 GB | ~500₽/мес |
| **Selectel** | Стандарт | 2 vCPU | 4 GB | 40 GB | ~600₽/мес |

> **Рекомендация**: Hetzner CX22 — лучшее соотношение цена/качество. Дата-центр: Финляндия (fsn1) — ближайший к России.

### Что ещё нужно

- **Anthropic API ключ** — для Claude Code (~$5-20/мес в зависимости от использования)
- **Telegram Bot Token** — бесплатно, от @BotFather
- **Домен** — не обязателен (бот работает без него)

---

## 3. Первоначальная настройка сервера

### 3.1 Подключение

```bash
ssh root@ВАШ_IP
```

### 3.2 Обновление системы

```bash
apt update && apt upgrade -y
```

### 3.3 Создание пользователя

```bash
# Создать пользователя для бота (НЕ работать от root)
adduser claude
usermod -aG sudo claude

# Переключиться на нового пользователя
su - claude
```

### 3.4 Установка базовых пакетов

```bash
# Node.js 22 (для Claude Code)
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs

# Python 3.12 + инструменты
sudo apt install -y python3 python3-pip python3-venv python3-dev

# Git, Docker, утилиты
sudo apt install -y git curl wget unzip htop jq ffmpeg

# Docker (для MCP серверов и проектов)
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker claude
```

### 3.5 Swap файл (если RAM < 4GB)

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### 3.6 SSH ключи

```bash
# На ЛОКАЛЬНОЙ машине (не на VPS)
ssh-keygen -t ed25519 -C "claude-bot-vps"
ssh-copy-id -i ~/.ssh/id_ed25519.pub claude@ВАШ_IP
```

---

## 4. Hardening безопасности

### 4.1 SSH Hardening

```bash
sudo nano /etc/ssh/sshd_config
```

Изменить/добавить:

```
Port 2222                          # Сменить порт (не 22)
PermitRootLogin no                 # Запретить вход root
PasswordAuthentication no          # Только ключи
PubkeyAuthentication yes
MaxAuthTries 3
AllowUsers claude                  # Только наш пользователь
```

```bash
sudo systemctl restart sshd
```

> **ВАЖНО**: Перед перезапуском sshd откройте ВТОРОЙ терминал и проверьте что можете войти по ключу на новом порту: `ssh -p 2222 claude@ВАШ_IP`

### 4.2 Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 2222/tcp comment 'SSH'
# НЕ открывать другие порты без необходимости
sudo ufw enable
```

### 4.3 Fail2ban (защита от брутфорса)

```bash
sudo apt install -y fail2ban

sudo tee /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3

[sshd]
enabled = true
port = 2222
filter = sshd
logpath = /var/log/auth.log
maxretry = 3
bantime = 86400
EOF

sudo systemctl enable fail2ban
sudo systemctl start fail2ban
```

### 4.4 Автообновления безопасности

```bash
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades
```

### 4.5 Изоляция бота

```bash
# Бот работает от пользователя claude (не root)
# Ограничить доступ к системным директориям
# claude НЕ должен быть в группе sudo в продакшене
# (убрать sudo после настройки):
# sudo deluser claude sudo
```

### 4.6 Чек-лист безопасности

- [ ] SSH по ключам, пароли отключены
- [ ] SSH порт изменён (не 22)
- [ ] Root вход запрещён
- [ ] UFW включён, открыт только SSH
- [ ] Fail2ban работает
- [ ] Автообновления включены
- [ ] Бот работает от непривилегированного пользователя
- [ ] Нет открытых портов кроме SSH

---

## 5. Установка Claude Code

### 5.1 Установка

```bash
# От пользователя claude
npm install -g @anthropic-ai/claude-code
```

### 5.2 Авторизация

Claude Code использует OAuth — авторизацию через аккаунт Anthropic (подписка Claude Max/Pro).

```bash
# Авторизация через браузер
claude auth login

# На headless VPS — получить ссылку и открыть на другом устройстве
claude auth login
# Скопировать URL → открыть в браузере → авторизоваться
```

### 5.3 Проверка

```bash
claude -p "Ответь: привет мир" --output-format text
# Должно вывести ответ Claude
```

### 5.4 Настройка settings.json

```bash
mkdir -p ~/.claude
# Скопировать конфиг MCP серверов (см. раздел 10)
cp configs/claude-settings.json ~/.claude/settings.json
```

---

## 6. Код Telegram-бота

Полный код бота находится в файле `bot.py` (в этой же директории).

### Основные возможности

- Текстовые сообщения → Claude Code CLI
- Голосовые сообщения → STT → Claude → TTS → голосовой ответ
- Фото → OCR/описание → Claude
- Сессии (память между сообщениями)
- Мульти-проект (переключение `/project`)
- Мульти-юзер с ролями
- Отмена запросов (`/cancel`)
- Лимиты сообщений в день

### Команды бота

| Команда | Описание |
|---------|----------|
| `/start` | Приветствие и справка |
| `/new` | Новая сессия (сбросить контекст) |
| `/cancel` | Отменить текущий запрос |
| `/session` | Показать ID сессии |
| `/project` | Список проектов |
| `/project <имя>` | Переключиться на проект |
| `/voice on/off` | Включить/выключить голосовые ответы |
| `/users` | Управление пользователями (admin) |
| `/stats` | Статистика использования (admin) |

### Установка зависимостей

```bash
cd /home/claude/claude-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## 7. Голосовой режим (STT + TTS)

### Как работает

```
🎤 Голосовое сообщение
       │
       ▼
  Скачать .ogg из Telegram
       │
       ▼
  ffmpeg: .ogg → .wav
       │
       ▼
  faster-whisper: .wav → текст
       │
       ▼
  Claude Code: текст → ответ
       │
       ▼
  edge-tts: ответ → .mp3
       │
       ▼
  Отправить голосовое + текст в Telegram
```

### Установка STT (faster-whisper)

```bash
# В venv бота
pip install faster-whisper

# Первый запуск скачает модель (~500MB)
# Модель: base — баланс скорость/качество
# Модель: small — лучше качество, больше RAM
```

### Установка TTS (edge-tts)

```bash
pip install edge-tts

# Проверка
edge-tts --voice ru-RU-DmitryNeural --text "Привет мир" --write-media test.mp3
```

### Доступные русские голоса

| Голос | Пол | Описание |
|-------|-----|----------|
| `ru-RU-DmitryNeural` | Мужской | Чёткий, нейтральный |
| `ru-RU-SvetlanaNeural` | Женский | Мягкий, приятный |

### Требования к ресурсам

| Компонент | RAM | CPU | Примечание |
|-----------|-----|-----|------------|
| faster-whisper (base) | ~500 MB | Средняя нагрузка | Первый запуск скачивает модель |
| faster-whisper (small) | ~1 GB | Высокая нагрузка | Лучше качество |
| edge-tts | ~10 MB | Минимальная | Работает через API Microsoft |

> **Если RAM не хватает**: использовать модель `tiny` (~200MB) или отказаться от STT и использовать Telegram Premium (встроенная транскрибация).

---

## 8. Работа с фото и картинками

### Как работает

```
📷 Фото в Telegram
       │
       ▼
  Скачать файл
       │
       ├──→ Tesseract OCR → текст из фото
       │
       └──→ Описание фото (caption от пользователя)
                │
                ▼
           Claude Code: "На фото: [OCR текст]. Задача: [caption]"
                │
                ▼
           Ответ → Telegram
```

### Установка OCR

```bash
# Tesseract для извлечения текста с изображений
sudo apt install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng

# Python-обёртка
pip install pytesseract Pillow
```

### Сценарии использования

| Сценарий | Что отправить | Что получишь |
|----------|--------------|--------------|
| Скриншот ошибки | Фото + "исправь" | Анализ ошибки и решение |
| Фото документа | Фото + "извлеки текст" | Текст из документа |
| Схема/диаграмма | Фото + "опиши" | Текстовое описание |
| Код с экрана | Фото + "что делает этот код" | Объяснение кода |

### Ограничения

- Claude Code CLI (`-p` режим) не поддерживает отправку картинок напрямую
- Обходной путь: OCR + текстовое описание (реализовано в боте)
- Для полноценного vision: использовать Claude API напрямую (через Anthropic SDK) вместо CLI

---

## 9. Мульти-юзер режим

### Роли

| Роль | Права | Описание |
|------|-------|----------|
| `admin` | Все | Полный доступ, управление пользователями |
| `user` | Чтение + запись | Работа со своими проектами |
| `readonly` | Только чтение | Вопросы по коду, без изменений |

### Как работает

```
Пользователь A (admin):
  - Проекты: все
  - --dangerously-skip-permissions
  - Лимит: без ограничений

Пользователь B (user):
  - Проекты: только ~/projects/user_b/
  - --dangerously-skip-permissions
  - Лимит: 50 сообщений/день

Пользователь C (readonly):
  - Проекты: только чтение ~/projects/shared/
  - БЕЗ --dangerously-skip-permissions (только чтение)
  - Лимит: 20 сообщений/день
```

### Конфигурация

В файле `.env`:

```bash
# Формат: ID:роль:лимит_в_день
# admin — без лимита (0 = безлимит)
USERS='{"123456789": {"role": "admin", "limit": 0, "name": "Имя"}, "987654321": {"role": "user", "limit": 50, "name": "Коллега"}}'
```

### Изоляция

- Каждый пользователь работает в своей директории
- Сессии Claude Code раздельные
- Логи раздельные
- `readonly` пользователи не могут менять файлы (Claude запускается без `--dangerously-skip-permissions`)

---

## 10. MCP серверы (бесплатные)

MCP (Model Context Protocol) — плагины, расширяющие возможности Claude Code.

### Полный список бесплатных MCP серверов

#### Разработка и код

| MCP сервер | NPM пакет | Что делает | Применение |
|------------|-----------|-----------|------------|
| **GitHub** | `@modelcontextprotocol/server-github` | GitHub API | PR, issues, код-ревью, поиск кода |
| **GitLab** | `@modelcontextprotocol/server-gitlab` | GitLab API | То же для GitLab |
| **Filesystem** | `@modelcontextprotocol/server-filesystem` | Расширенная работа с файлами | Поиск, чтение, запись за пределами CWD |
| **Docker** | Встроенный | Управление Docker | Контейнеры, образы, логи |
| **SQLite** | `@modelcontextprotocol/server-sqlite` | SQLite базы данных | Локальная аналитика, хранение данных |
| **PostgreSQL** | `@modelcontextprotocol/server-postgres` | PostgreSQL | Работа с БД проектов |

#### Браузер и веб

| MCP сервер | NPM пакет | Что делает | Применение |
|------------|-----------|-----------|------------|
| **Playwright** | `@anthropic-ai/mcp-server-playwright` | Headless браузер | Тестирование UI, скриншоты, парсинг |
| **Puppeteer** | `@modelcontextprotocol/server-puppeteer` | Headless браузер (альтернатива) | Скриншоты, PDF |
| **Fetch** | `@modelcontextprotocol/server-fetch` | HTTP запросы | Загрузка данных, API |

#### Поиск и информация

| MCP сервер | NPM пакет | Что делает | Применение |
|------------|-----------|-----------|------------|
| **Brave Search** | `@modelcontextprotocol/server-brave-search` | Поиск в интернете | Актуальная информация (нужен бесплатный API ключ) |
| **YouTube Transcript** | `mcp-youtube-transcript` | Субтитры YouTube | Извлечение текста из видео |
| **Arxiv** | `mcp-server-arxiv` | Научные статьи | Поиск и чтение исследований |

#### Продуктивность

| MCP сервер | NPM пакет | Что делает | Применение |
|------------|-----------|-----------|------------|
| **Memory** | `@modelcontextprotocol/server-memory` | Долгосрочная память | Хранение контекста между сессиями |
| **Sequential Thinking** | `@modelcontextprotocol/server-sequential-thinking` | Сложные рассуждения | Пошаговый анализ, планирование |
| **Google Maps** | `@modelcontextprotocol/server-google-maps` | Карты | Поиск мест, маршруты (бесплатный тир) |

### Конфигурация

Файл `~/.claude/settings.json` (полный пример в `configs/claude-settings.json`):

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_..."
      }
    },
    "playwright": {
      "command": "npx",
      "args": ["-y", "@anthropic-ai/mcp-server-playwright"]
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "/home/claude/projects"]
    },
    "sqlite": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "/home/claude/data/analytics.db"]
    },
    "fetch": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-fetch"]
    },
    "memory": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-memory"]
    },
    "sequential-thinking": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-sequential-thinking"]
    },
    "brave-search": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-brave-search"],
      "env": {
        "BRAVE_API_KEY": "BSA..."
      }
    },
    "youtube-transcript": {
      "command": "npx",
      "args": ["-y", "mcp-youtube-transcript"]
    }
  }
}
```

### Получение бесплатных API ключей

| Сервис | Где получить | Бесплатный лимит |
|--------|-------------|-----------------|
| **GitHub PAT** | github.com → Settings → Developer Settings → Personal Access Tokens | Безлимит |
| **Brave Search** | brave.com/search/api | 2000 запросов/мес |
| **Google Maps** | console.cloud.google.com | $200/мес кредит |

---

## 11. Systemd и автозапуск

### Unit файл

Файл `/etc/systemd/system/claude-bot.service`:

```ini
[Unit]
Description=Claude Code Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=claude
Group=claude
WorkingDirectory=/home/claude/claude-bot
EnvironmentFile=/home/claude/claude-bot/.env
ExecStart=/home/claude/claude-bot/venv/bin/python bot.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=claude-bot

# Безопасность
NoNewPrivileges=yes
ProtectSystem=strict
ReadWritePaths=/home/claude

[Install]
WantedBy=multi-user.target
```

### Управление

```bash
# Установить и запустить
sudo cp claude-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable claude-bot
sudo systemctl start claude-bot

# Проверить статус
sudo systemctl status claude-bot

# Логи
sudo journalctl -u claude-bot -f              # Следить в реальном времени
sudo journalctl -u claude-bot --since today    # За сегодня
sudo journalctl -u claude-bot -n 100           # Последние 100 строк

# Перезапуск
sudo systemctl restart claude-bot

# Остановка
sudo systemctl stop claude-bot
```

---

## 12. Бэкапы и восстановление

### Что бэкапить

| Что | Путь | Важность |
|-----|------|----------|
| Код бота | `/home/claude/claude-bot/` | Средняя (есть в git) |
| Проекты | `/home/claude/projects/` | Высокая |
| Конфиги Claude | `~/.claude/` | Высокая |
| Env файл | `/home/claude/claude-bot/.env` | Критическая |
| Systemd unit | `/etc/systemd/system/claude-bot.service` | Низкая (легко воссоздать) |

### Скрипт автоматического бэкапа

Файл `scripts/backup.sh` (в этой же директории).

```bash
# Добавить в cron (ежедневно в 3:00)
crontab -e
# Добавить строку:
0 3 * * * /home/claude/claude-bot/scripts/backup.sh >> /home/claude/backups/backup.log 2>&1
```

### Восстановление на новом VPS

```bash
# 1. Настроить сервер (разделы 3-5)
# 2. Скопировать бэкап
scp backup-YYYY-MM-DD.tar.gz claude@НОВЫЙ_IP:/home/claude/

# 3. Распаковать
cd /home/claude
tar xzf backup-YYYY-MM-DD.tar.gz

# 4. Установить зависимости
cd claude-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 5. Запустить
sudo systemctl enable claude-bot
sudo systemctl start claude-bot
```

---

## 13. Мониторинг и алерты

### Healthcheck скрипт

Файл `scripts/healthcheck.sh` — проверяет что бот работает и отправляет алерт в Telegram если упал.

```bash
# Добавить в cron (каждые 5 минут)
crontab -e
*/5 * * * * /home/claude/claude-bot/scripts/healthcheck.sh
```

### Что мониторится

| Метрика | Порог | Действие |
|---------|-------|----------|
| Бот запущен | — | Алерт если упал |
| Диск | > 80% | Алерт |
| RAM | > 90% | Алерт |
| CPU | > 95% (5 мин) | Алерт |
| Бэкап свежий | < 24 часов | Алерт если старый |

### Скрипт мониторинга

Файл `scripts/healthcheck.sh` (в этой же директории).

---

## 14. Обновление и обслуживание

### Обновление Claude Code

```bash
npm update -g @anthropic-ai/claude-code
claude --version  # Проверить новую версию
sudo systemctl restart claude-bot
```

### Обновление MCP серверов

```bash
# Очистить кэш npx (скачает свежие версии при следующем запуске)
npx clear-npx-cache
sudo systemctl restart claude-bot
```

### Обновление бота

```bash
cd /home/claude/claude-bot
# Если бот в git
git pull

# Обновить зависимости
source venv/bin/activate
pip install -r requirements.txt --upgrade

sudo systemctl restart claude-bot
```

### Обновление системы

```bash
sudo apt update && sudo apt upgrade -y
# Перезагрузка если обновилось ядро
sudo reboot
```

### Скрипт обновления всего

Файл `scripts/update.sh` (в этой же директории).

---

## 15. Troubleshooting

### Бот не отвечает

```bash
# 1. Проверить статус
sudo systemctl status claude-bot

# 2. Посмотреть логи
sudo journalctl -u claude-bot -n 50

# 3. Проверить что claude работает
su - claude
claude -p "test" --output-format text

# 4. Перезапустить
sudo systemctl restart claude-bot
```

### Claude Code не авторизуется

```bash
# Проверить статус авторизации
claude auth status

# Переавторизоваться
claude auth login
```

### Голосовые сообщения не работают

```bash
# Проверить ffmpeg
ffmpeg -version

# Проверить faster-whisper
python3 -c "from faster_whisper import WhisperModel; print('OK')"

# Проверить edge-tts
edge-tts --list-voices | grep ru-RU
```

### Не хватает RAM

```bash
# Проверить
free -h

# Увеличить swap
sudo swapoff /swapfile
sudo fallocate -l 4G /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile

# Использовать модель whisper поменьше (tiny вместо base)
# В bot.py: WHISPER_MODEL = "tiny"
```

### MCP сервер не запускается

```bash
# Тест вручную
npx -y @modelcontextprotocol/server-github

# Проверить что Node.js установлен
node --version  # Должен быть 18+

# Очистить кэш
npx clear-npx-cache
```

### Firewall заблокировал доступ

```bash
# Если заблокировали себя — через консоль VPS провайдера:
ufw allow 2222/tcp
ufw enable

# Проверить правила
sudo ufw status verbose
```

### Бот отвечает медленно

- Claude Code думает 10-60 секунд — это нормально
- Если > 2 минут — проблема с сетью или перегрузка API
- Проверить: `time claude -p "привет" --output-format text`

### Ошибка "Too many requests"

- Anthropic API rate limit
- Решение: уменьшить лимит сообщений в настройках мульти-юзера
- Или перейти на более высокий тарифный план Anthropic

---

## Локальная машина vs VPS

Бот одинаково работает локально и на VPS. Разница — в окружении и настройке.

### Таблица сравнения

| Аспект | Локально | VPS |
|--------|----------|-----|
| **Время настройки** | 5 минут | 30-60 минут |
| **Доступность** | Пока комп включён | 24/7 |
| **Безопасность сервера** | Не нужна (нет внешнего IP) | Обязательна (разделы 3-4) |
| **Systemd** | По желанию | Обязательно (раздел 11) |
| **Бэкапы** | Не критично (всё на месте) | Критично (раздел 12) |
| **Мониторинг** | Не нужен (видишь в терминале) | Нужен (раздел 13) |
| **Стоимость** | $0 (кроме API) | €4-8/мес + API |
| **Создание пользователя** | Не нужно (работаешь от себя) | Нужно (раздел 3) |
| **SSH hardening** | Не нужен | Обязателен |
| **Firewall** | Не нужен | Обязателен |

### Что пропускать при локальной установке

Разделы для **только VPS** (пропустить при локальной установке):
- ~~Раздел 2~~ — Требования к VPS (у тебя уже есть машина)
- ~~Раздел 3~~ — Настройка сервера (всё уже установлено)
- ~~Раздел 4~~ — Hardening безопасности (нет внешнего IP)
- ~~Раздел 11~~ — Systemd (запускаешь вручную в терминале)
- ~~Раздел 12~~ — Бэкапы (файлы уже на твоей машине)
- ~~Раздел 13~~ — Мониторинг (видишь логи в терминале)

Разделы, которые **нужны и локально и на VPS**:
- Раздел 5 — Установка Claude Code (уже есть ✅)
- Раздел 6 — Код бота
- Раздел 7 — Голосовой режим
- Раздел 8 — Работа с фото
- Раздел 9 — Мульти-юзер
- Раздел 10 — MCP серверы

---

## Локальное развёртывание

> Для быстрого запуска на своей машине. Не нужен VPS, не нужен hardening, не нужен systemd.

### Что уже есть на твоей машине

| Компонент | Статус | Примечание |
|-----------|--------|-----------|
| Python 3.12 | ✅ Установлен | |
| Node.js 20 | ✅ Установлен | |
| Claude Code | ✅ Установлен и авторизован | |
| ffmpeg | ❌ Не установлен | Нужен для голосовых |
| tesseract | ❌ Не установлен | Нужен для OCR фото |

### Шаг 1: Доустановить недостающее

```bash
# ffmpeg (для голосовых сообщений)
sudo apt install -y ffmpeg

# tesseract (для OCR фото)
sudo apt install -y tesseract-ocr tesseract-ocr-rus tesseract-ocr-eng
```

Или автоматически:

```bash
bash /home/bgs/Henry_Bud_GitHub/claude_bot/scripts/setup-local.sh
```

> Если голос и фото не нужны — этот шаг можно пропустить. Бот будет работать только с текстом.

### Шаг 2: Создать виртуальное окружение

```bash
cd /home/bgs/Henry_Bud_GitHub/claude_bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Шаг 3: Настроить .env

```bash
cp .env.example .env
nano .env  # или любой редактор
```

Заполнить:
- `TELEGRAM_BOT_TOKEN` — получить у @BotFather
- `PROJECTS_DIR` — путь к папке с проектами (например `/home/bgs/Henry_Bud_GitHub`)
- `USERS` — оставить пустым `{}` для режима без ограничений, или указать свой Telegram ID

### Шаг 4: Запустить

```bash
cd /home/bgs/Henry_Bud_GitHub/claude_bot
source venv/bin/activate
export $(grep -v '^#' .env | xargs)
python bot.py
```

Бот запущен. Открой Telegram → найди своего бота → `/start`.

### Шаг 5: Остановить

`Ctrl+C` в терминале.

### Запуск в фоне (без systemd)

Если не хочешь держать терминал открытым:

```bash
# Вариант 1: nohup
cd /home/bgs/Henry_Bud_GitHub/claude_bot
source venv/bin/activate
export $(grep -v '^#' .env | xargs)
nohup python bot.py > bot.log 2>&1 &
echo $! > bot.pid

# Остановить
kill $(cat bot.pid)

# Вариант 2: tmux/screen
tmux new -s claude-bot
cd /home/bgs/Henry_Bud_GitHub/claude_bot
source venv/bin/activate
export $(grep -v '^#' .env | xargs)
python bot.py
# Ctrl+B, D — отключиться от сессии
# tmux attach -t claude-bot — вернуться
```

### Когда переезжать на VPS

Переезжай на VPS когда:
- Хочешь чтобы бот работал 24/7 (а не только пока комп включён)
- Хочешь дать доступ другим людям
- Хочешь запускать долгие задачи (деплой, тесты) пока спишь
- Надоело запускать вручную

Для переезда: следуй разделам 2-5 и 11 из основной инструкции.

---

## Быстрый старт — VPS (TL;DR)

Если хочешь запустить на VPS за 30 минут без всех наворотов:

```bash
# 1. Купить VPS (Hetzner CX22, €4.35/мес)
# 2. Подключиться
ssh root@IP

# 3. Настроить
adduser claude && su - claude
curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
sudo apt install -y nodejs python3 python3-venv ffmpeg
npm install -g @anthropic-ai/claude-code

# 4. Авторизовать Claude (OAuth через браузер)
claude auth login

# 5. Запустить бота
mkdir ~/claude-bot && cd ~/claude-bot
python3 -m venv venv && source venv/bin/activate
pip install aiogram faster-whisper edge-tts pytesseract Pillow
# Скопировать bot.py и .env
# Настроить .env
python bot.py
```

---

*Версия документа: 1.1 | Дата: 2026-03-05*
