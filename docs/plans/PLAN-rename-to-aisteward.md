# План: Переименование claude_bot → aisteward

## Context

Проект `claude_bot` привязан к одной LLM (Claude). Планируется поддержка нескольких AI-моделей (Codex и др.). Нужно:
1. Переименовать проект в `aisteward` (универсальное название)
2. Создать общую директорию `/home/bgs/aisteward/` для пользовательских воркспейсов с общим `CLAUDE.md`

Проект развёрнут на: **локальной машине** (`/opt/claude_bot`), **GitHub** (`bgs2509/claude_bot`), **VPS** (`/opt/claude_bot`, systemd service `claude-bot`).

## Стратегия

**Поэтапно, двумя коммитами:**
- **Коммит 1** (Фазы 0-3, 6-8): переименование пакета, сервиса, скриптов, доков, деплой
- **Коммит 2** (Фаза 4): создание воркспейсов `/home/bgs/aisteward/`, перенос пользовательских директорий

Директория проекта: `/opt/claude_bot` → **`/opt/aisteward`**

---

## Масштаб изменений

| Категория | Кол-во | Критичность |
|-----------|--------|-------------|
| Директория пакета (`src/claude_bot/` → `src/aisteward/`) | 1 | CRITICAL |
| pyproject.toml (имя, entry point, packages) | 3 строки | CRITICAL |
| Python import statements | 85+ | CRITICAL |
| Logger names (`"claude-bot.*"`) | 22 | HIGH |
| systemd service file (rename + содержимое) | 1 файл, 5 строк | CRITICAL |
| Makefile | 6 строк | HIGH |
| Scripts (setup, backup, healthcheck, update) | 11 строк | HIGH |
| Документация (README, CLAUDE.md, CHANGELOG, docs/) | 115+ | MEDIUM |
| Git remote URL | 1 | HIGH |
| Директория проекта `/opt/claude_bot` → `/opt/aisteward` | 1 | HIGH |
| Пользовательские воркспейсы → `/home/bgs/aisteward/` | 5 юзеров | HIGH |
| users.json (projects_dir) | 5 записей | HIGH |

---

## Порядок выполнения

### Фаза 0: Подготовка и бэкап

1. **На VPS**: остановить сервис
   ```bash
   ssh vps "sudo systemctl stop claude-bot"
   ```

2. **Бэкап** (локально + VPS):
   ```bash
   # Локально
   cp -r /opt/claude_bot /opt/claude_bot.bak
   # VPS (если отличается)
   ssh vps "cp -r /opt/claude_bot /opt/claude_bot.bak"
   ```

3. **Бэкап пользовательских данных**:
   ```bash
   cp /opt/claude_bot/data/sessions.json /opt/claude_bot/data/sessions.json.bak
   cp /opt/claude_bot/data/users.json /opt/claude_bot/data/users.json.bak
   ```

---

### Фаза 1: Переименование Python-пакета (локально)

**Критические файлы:**

#### 1.1 Переименовать директорию пакета
```bash
mv src/claude_bot src/aisteward
```

#### 1.2 Обновить `pyproject.toml`
```
- name = "claude-bot"          → name = "aisteward"
- claude-bot = "claude_bot..." → aisteward = "aisteward.__main__:main"
- packages = ["src/claude_bot"] → packages = ["src/aisteward"]
```

#### 1.3 Обновить все import statements (85+)
Массовая замена во всех `.py` файлах:
```
from claude_bot. → from aisteward.
import claude_bot. → import aisteward.
```

Файлы (все в `src/aisteward/` после переименования):
- `__main__.py`, `bot.py`, `config.py`, `keyboards.py`, `logging_setup.py`, `state.py`
- `handlers/`: `__init__.py`, `commands.py`, `document.py`, `menu.py`, `photo.py`, `project_switch.py`, `text.py`, `upload.py`, `voice.py`
- `services/`: `analytics.py`, `claude.py`, `format_telegram.py`, `notification_manager.py`, `notification_service.py`, `ocr.py`, `planner_formatter.py`, `planner_manager.py`, `planner_service.py`, `speech.py`, `storage.py`, `upload.py`
- `middlewares/`: `auth.py`, `error.py`, `observability.py`

#### 1.4 Обновить logger names (22 вхождения)
```
"claude-bot" → "aisteward"
"claude-bot.storage" → "aisteward.storage"
... (по тому же паттерну)
```

#### 1.5 Обновить `__main__.py`
- Docstring: `python -m claude_bot` → `python -m aisteward`
- Startup log: `service=claude-bot` → `service=aisteward`

#### 1.6 Обновить `.claude/settings.local.json`
- Строка 14: `from claude_bot...` → `from aisteward...`

---

### Фаза 2: Переименование сервиса и конфигурации

#### 2.1 Переименовать файл сервиса
```bash
mv claude-bot.service aisteward.service
```

#### 2.2 Обновить содержимое `aisteward.service`
```
Description=Claude Code Telegram Bot → Description=AI Steward Telegram Bot
WorkingDirectory=/opt/claude_bot → /opt/aisteward
ExecStart=...claude-bot → ...aisteward
SyslogIdentifier=claude-bot → aisteward
```

#### 2.3 Обновить `Makefile`
```
uv run claude-bot → uv run aisteward
claude-bot.service → aisteward.service
systemctl ... claude-bot → systemctl ... aisteward
journalctl -u claude-bot → journalctl -u aisteward
```

---

### Фаза 3: Обновление скриптов

#### 3.1 `scripts/setup-local.sh`
- `uv run claude-bot` → `uv run aisteward`

#### 3.2 `scripts/update.sh`
- `/home/claude/claude-bot` → `/opt/aisteward`
- `systemctl restart claude-bot` → `systemctl restart aisteward`
- `systemctl is-active claude-bot` → `systemctl is-active aisteward`

#### 3.3 `scripts/healthcheck.sh`
- Все `claude-bot` → `aisteward`
- Путь cron-комментария

#### 3.4 `scripts/backup.sh`
- Путь `/home/claude/claude-bot/` → `/opt/aisteward/`
- Cron-комментарий

---

### Фаза 4: Создание воркспейс-директории

Это ключевая архитектурная часть — общая директория для всех пользователей с общим `CLAUDE.md`.

#### 4.1 Создать структуру
```bash
mkdir -p /home/bgs/aisteward
```

#### 4.2 Создать общий `CLAUDE.md` (уровень бота для ВСЕХ юзеров)
```
/home/bgs/aisteward/CLAUDE.md
```
Содержимое: правила сбора информации о пользователе, структура папок проекта, формат ответов, общие правила безопасности.

#### 4.3 Переместить пользовательские директории
```bash
mv /home/bgs/Henry_Bud_GitHub /home/bgs/aisteward/Henry_Bud
mv /home/bgs/_Gena_MTS        /home/bgs/aisteward/Gena_MTS
mv /home/bgs/_Dari            /home/bgs/aisteward/Dari
mv /home/bgs/_Marat           /home/bgs/aisteward/Marat
mv /home/bgs/_Tania           /home/bgs/aisteward/Tania
```

**ВНИМАНИЕ**: `/home/bgs/Henry_Bud_GitHub` содержит Git-репозитории (включая `python-ai-skills`). Нужно убедиться что симлинки и `.git` remote URL не сломаются.

#### 4.4 Обновить `data/users.json`
```json
{
    "763463467":  { "projects_dir": "/home/bgs/aisteward/Henry_Bud" },
    "6156629438": { "projects_dir": "/home/bgs/aisteward/Gena_MTS" },
    "1122408606": { "projects_dir": "/home/bgs/aisteward/Dari" },
    "1317941844": { "projects_dir": "/home/bgs/aisteward/Marat" },
    "1151678530": { "projects_dir": "/home/bgs/aisteward/Tania" }
}
```

#### 4.5 Обновить `users.json.example`

#### 4.6 Обновить systemd `ReadWritePaths`
В `aisteward.service`:
```
ReadWritePaths=/opt/aisteward /home/bgs/aisteward /home/bgs/.claude /home/bgs/.local
```

#### 4.7 Обновить CLAUDE.md (глобальный `~/.claude/CLAUDE.md`)
Раздел "LOCAL-ONLY EXECUTION" — исключение для записи:
```
Путь: ~/aisteward/**  (вместо ~/Henry_Bud_GitHub/python-ai-skills/**)
```

---

### Фаза 5: Иерархия CLAUDE.md (результат)

После всех изменений, Claude Code CLI запущенный с `cwd=/home/bgs/aisteward/Henry_Bud/Health` автоматически прочитает:

```
1. ~/.claude/CLAUDE.md                          ← Глобальный (машина)
2. /home/bgs/aisteward/CLAUDE.md                ← Уровень бота (ВСЕ юзеры) [NEW]
3. /home/bgs/aisteward/Henry_Bud/CLAUDE.md      ← Пользовательский
4. /home/bgs/aisteward/Henry_Bud/Health/CLAUDE.md ← Проект
```

---

### Фаза 6: Документация

#### 6.1 Обновить `CLAUDE.md` (проектный)
- `# claude_bot` → `# aisteward`
- Все пути `src/claude_bot/` → `src/aisteward/`
- `make run` команда

#### 6.2 Обновить `README.md`
- Название, описание, пути, команды

#### 6.3 Обновить `CHANGELOG.md`
- Добавить запись в `[Unreleased]`:
  ```
  ### Changed
  - Проект переименован из claude_bot в aisteward
  ```

#### 6.4 Обновить `docs/DEPLOYMENT.md`
- Все 40+ вхождений `claude-bot` / `claude_bot`

#### 6.5 Обновить `docs/USAGE.md`, `docs/ROADMAP.md`, `docs/adr/*.md`

---

### Фаза 7: Git и GitHub

#### 7.1 Переименовать репозиторий на GitHub
- GitHub → Settings → Repository name: `claude_bot` → `aisteward`
- GitHub автоматически настроит редирект со старого URL

#### 7.2 Обновить remote локально
```bash
git remote set-url origin git@github.com:bgs2509/aisteward.git
```

#### 7.3 Переместить локальную директорию
```bash
mv /opt/claude_bot /opt/aisteward
```

#### 7.4 Коммит
```
feat: rename project from claude_bot to aisteward
```

---

### Фаза 8: Развёртывание на VPS

#### 8.1 Остановить старый сервис
```bash
ssh vps "sudo systemctl stop claude-bot && sudo systemctl disable claude-bot"
```

#### 8.2 Переместить директорию на VPS
```bash
ssh vps "mv /opt/claude_bot /opt/aisteward"
```

#### 8.3 Синхронизировать код
```bash
ssh vps "cd /opt/aisteward && git pull"
```

#### 8.4 Переустановить зависимости
```bash
ssh vps "cd /opt/aisteward && uv sync"
```

#### 8.5 Установить новый сервис
```bash
ssh vps "sudo cp /opt/aisteward/aisteward.service /etc/systemd/system/"
ssh vps "sudo systemctl daemon-reload"
ssh vps "sudo systemctl enable aisteward"
ssh vps "sudo systemctl start aisteward"
```

#### 8.6 Удалить старый сервис
```bash
ssh vps "sudo rm /etc/systemd/system/claude-bot.service"
```

#### 8.7 Создать воркспейсы на VPS
Повторить Фазу 4 на VPS (если пользовательские директории там).

#### 8.8 Обновить cron (если настроен)
```bash
# Обновить пути в crontab
crontab -e
# /opt/claude_bot → /opt/aisteward
# claude-bot → aisteward
```

---

### Фаза 9: Обновление Claude Code memory

#### 9.1 Обновить `/home/bgs/.claude/projects/-opt-claude-bot/memory/`
- Перенести или обновить memory файлы для нового пути проекта
- Claude Code создаст новую директорию `/home/bgs/.claude/projects/-opt-aisteward/` автоматически

---

## Верификация

### Проверка после Фазы 1-3 (локально):
```bash
cd /opt/aisteward
uv sync                    # Зависимости устанавливаются?
uv run aisteward --help    # CLI запускается?
python -m aisteward        # Модуль запускается?
```

### Проверка после Фазы 4 (воркспейсы):
```bash
ls /home/bgs/aisteward/CLAUDE.md              # Общий CLAUDE.md существует?
ls /home/bgs/aisteward/Henry_Bud/CLAUDE.md    # Пользовательский на месте?
ls /home/bgs/aisteward/Henry_Bud/Health/       # Проекты на месте?
```

### Проверка после Фазы 8 (VPS):
```bash
ssh vps "sudo systemctl status aisteward"      # Сервис запущен?
ssh vps "journalctl -u aisteward --since '1 min ago'"  # Логи без ошибок?
# Отправить тестовое сообщение боту в Telegram
# Проверить переключение проектов
# Проверить планировщик (planner)
```

### Полный чеклист:
- [ ] `uv run aisteward` запускается локально
- [ ] Бот отвечает в Telegram
- [ ] Переключение проектов работает (кнопки)
- [ ] Claude Code CLI вызывается с правильным `cwd`
- [ ] `CLAUDE.md` из `/home/bgs/aisteward/` читается в сессиях
- [ ] Планировщик находит `planner.json` во всех проектах
- [ ] Напоминания отправляются
- [ ] Голосовые сообщения обрабатываются
- [ ] systemd сервис стабилен после перезагрузки VPS

---

## Риски и митигация

| Риск | Митигация |
|------|-----------|
| Пропущена ссылка на `claude_bot` | `grep -r "claude.bot\|claude_bot" /opt/aisteward/` после всех замен |
| Сломаны Git-репо в Henry_Bud_GitHub | Проверить `.git/config` в каждом sub-repo после перемещения |
| Claude Code memory потеряна | Скопировать из `-opt-claude-bot/` в `-opt-aisteward/` |
| sessions.json содержит старые пути проектов | Проверить — пути проектов там относительные (имя проекта, не полный путь) |
| VPS даунтайм | Выполнять в низкий трафик. Бэкап перед началом |
| `python-ai-skills` ссылается на старый путь | Проверить CLAUDE.md в `~/.claude/CLAUDE.md` → исключение для записи |

---

## Порядок выполнения (сводка)

```
0. Бэкап ──────────────────────────── 5 мин
1. Переименование пакета Python ──── 30 мин (основная работа)
2. Сервис + Makefile ──────────────── 10 мин
3. Скрипты ────────────────────────── 10 мин
4. Воркспейс /home/bgs/aisteward/ ── 15 мин
5. (верификация иерархии CLAUDE.md)
6. Документация ───────────────────── 20 мин
7. Git + GitHub ───────────────────── 5 мин
8. VPS деплой ─────────────────────── 15 мин
9. Memory ─────────────────────────── 5 мин
                                      ═══════
                                      ~2 часа
```
