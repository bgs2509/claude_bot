# PLAN-003: Скачивание видео из YouTube, RuTube, VK Video

**Task:** TASK-003
**Дата:** 2026-03-17

---

## Контекст

Пользователь хочет отправлять ссылки на видео (YouTube, RuTube, VK Video) в бот и получать видеофайл обратно. Бот должен определить доступные разрешения (144p–720p), предложить выбор через инлайн-клавиатуру, скачать и отправить. Стандартный Telegram Bot API ограничивает отправку файлов до 50MB, поэтому для поддержки видео до 2GB необходим Local Bot API сервер.

---

## Часть 1: Local Telegram Bot API

### Зачем

Стандартный Bot API: отправка до 50MB, скачивание до 20MB.
Local Bot API: отправка и скачивание до 2GB, файлы передаются по локальному пути (без HTTP upload).

### Требования

- `api_id` и `api_hash` — получить на https://my.telegram.org → "API development tools"
- Docker для запуска контейнера

### Инструкция получения api_id и api_hash

1. Открыть https://my.telegram.org
2. Ввести номер телефона (с кодом страны, например `+7XXXXXXXXXX`)
3. Ввести код подтверждения из Telegram-приложения (не SMS)
4. Нажать "API development tools"
5. Заполнить форму: App title — любое, Short name — любое, Platform — Desktop
6. Нажать "Create application"
7. Скопировать `api_id` (число) и `api_hash` (32-символьная строка)

### Docker-контейнер

Добавить сервис в существующий `docker-compose.yml` (или создать новый):

```yaml
services:
  telegram-bot-api:
    image: aiogram/telegram-bot-api:latest
    restart: unless-stopped
    environment:
      TELEGRAM_API_ID: "${TELEGRAM_API_ID}"
      TELEGRAM_API_HASH: "${TELEGRAM_API_HASH}"
    ports:
      - "8081:8081"
    volumes:
      - telegram-bot-api-data:/var/lib/telegram-bot-api

volumes:
  telegram-bot-api-data:
```

### Изменения в коде бота

**Файл:** `src/claude_bot/config.py`

Добавить поле:
```python
telegram_local_api_url: str | None = None  # например "http://localhost:8081"
```

**Файл:** `src/claude_bot/bot.py`

```python
def create_bot(settings: Settings) -> Bot:
    kwargs = {}
    if settings.telegram_local_api_url:
        kwargs["base_url"] = settings.telegram_local_api_url
    return Bot(token=settings.telegram_bot_token, **kwargs)
```

**Файл:** `.env.example`

Добавить:
```
# Local Bot API (опционально, для файлов > 50MB)
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_LOCAL_API_URL=http://localhost:8081
```

### Лимит файлов

С Local Bot API лимит — 2000MB. Без него — 50MB.
Бот должен определять лимит динамически:

```python
MAX_FILE_SIZE = 2000 * 1024 * 1024 if settings.telegram_local_api_url else 50 * 1024 * 1024
```

---

## Часть 2: Скачивание видео

### Новая зависимость

**Файл:** `pyproject.toml`

Добавить `yt-dlp>=2024.1.0`. Поддерживает YouTube, RuTube, VK Video из коробки.

### Новый файл: `src/claude_bot/services/video.py`

Сервис-обёртка над yt-dlp.

#### Regex для детекции URL

```python
VIDEO_URL_RE = re.compile(
    r"https?://(?:"
    r"(?:www\.)?youtube\.com/(?:watch\?v=|shorts/)[\w-]+"
    r"|youtu\.be/[\w-]+"
    r"|rutube\.ru/video/[\w-]+"
    r"|vk\.com/(?:video|clip)[\w.-]+"
    r")"
)
```

Покрытие:
- `youtube.com/watch?v=ID`, `youtu.be/ID`, `youtube.com/shorts/ID`
- `rutube.ru/video/HASH/`
- `vk.com/video-GID_VID`, `vk.com/clip-GID_CID`

#### Dataclasses

```python
@dataclass
class VideoFormat:
    format_id: str
    height: int           # 144, 240, 360, 480, 720
    filesize: int | None  # байты, None если неизвестен

@dataclass
class VideoInfo:
    title: str
    duration: int | None  # секунды
    formats: list[VideoFormat]
```

#### Функции

```python
MIN_HEIGHT = 144
MAX_HEIGHT = 720

async def fetch_formats(url: str) -> VideoInfo:
    """Запросить форматы через yt-dlp в executor (не блокирует event loop).

    Логика:
    1. loop.run_in_executor(None, _sync_fetch_formats, url)
    2. yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True}).extract_info(url, download=False)
    3. Из info["formats"] выбрать форматы с:
       - vcodec != "none" и acodec != "none" (video+audio в одном файле)
       - height в [MIN_HEIGHT, MAX_HEIGHT]
    4. Дедупликация по height — оставить лучший (наибольший filesize) для каждого разрешения
    5. Если merged форматов нет — собрать "синтетические" варианты:
       bestvideo[height<=720]+bestaudio, bestvideo[height<=480]+bestaudio и т.д.
    6. Сортировка по height по убыванию (720 → 480 → 360 → ...)
    """

async def download_video(url: str, format_id: str, output_dir: str) -> Path:
    """Скачать видео в executor.

    yt-dlp параметры:
    - format: format_id
    - outtmpl: output_dir + "/%(title).80s.%(ext)s"
    - quiet: True, no_warnings: True
    - merge_output_format: "mp4"  (если нужен merge)

    Таймаут: asyncio.wait_for(..., timeout=300) — 5 минут.
    Возвращает Path к скачанному файлу.
    """
```

### Новый файл: `src/claude_bot/handlers/video.py`

Роутер с FSM для двухшаговой обработки: обнаружение URL → выбор качества.

#### FSM

```python
class VideoDownload(StatesGroup):
    waiting_quality = State()
```

FSM хранит URL и список форматов между шагами. Callback data содержит только `vid:{format_id}` — URL берётся из FSM (избегаем лимита callback_data в 64 байта).

#### Хендлер 1: обнаружение URL

```python
@router.message(F.text.regexp(VIDEO_URL_RE))
async def handle_video_url(message, state, settings, app_state, project_tag, ...):
    # 1. Rate-limit (аналогично voice.py)
    # 2. Извлечь URL из текста через re.search
    # 3. Отправить waiting-сообщение: "🎬 Получаю информацию о видео..."
    # 4. fetch_formats(url) — в случае ошибки: "Не удалось получить информацию"
    # 5. Если formats пуст: "Нет доступных форматов 144p–720p"
    # 6. Сохранить url + formats в FSMContext
    # 7. Показать inline-клавиатуру: build_video_quality_keyboard(formats, max_file_size)
```

#### Хендлер 2: выбор качества

```python
@router.callback_query(F.data.startswith("vid:"), VideoDownload.waiting_quality)
async def handle_quality_pick(callback, state, settings, app_state, project_tag, ...):
    # 1. Прочитать format_id из callback.data
    # 2. Прочитать url из FSM, очистить FSM state
    # 3. Обработать "vid:cancel" — просто удалить сообщение
    # 4. Редактировать сообщение: "⬇️ Скачиваю видео..."
    # 5. download_video(url, format_id, tempfile.mkdtemp())
    # 6. Проверить размер файла vs MAX_FILE_SIZE
    # 7. Редактировать: "📤 Отправляю..."
    # 8. answer_video(FSInputFile(path))
    # 9. Cleanup: unlink файл, rmtree tmp_dir, удалить waiting-сообщение
```

#### Хендлер 3: отмена

```python
@router.callback_query(F.data == "vid:cancel", VideoDownload.waiting_quality)
async def handle_video_cancel(callback, state, ...):
    await state.clear()
    await callback.message.delete()
```

### Клавиатура: `keyboards.py`

```python
def build_video_quality_keyboard(
    formats: list[dict],
    max_file_size: int,
) -> InlineKeyboardMarkup:
    """Кнопки с разрешениями.

    Формат кнопки: "📹 720p (~15MB)" или "📹 720p" если размер неизвестен.
    Если filesize > max_file_size: "📹 720p (~150MB) ⚠️" — с предупреждением.
    Callback data: "vid:{format_id}" (обрезается до 58 символов для лимита 64 байта).
    Последняя кнопка: "❌ Отмена" → "vid:cancel".
    """
```

### Константы: `constants.py`

```python
VIDEO_CB_PREFIX = "vid:"
```

### Ошибки: `errors.py`

```python
"video_fetch_error": (
    "Не удалось получить информацию о видео.\n"
    "Возможные причины:\n"
    "• Видео недоступно или удалено\n"
    "• Ссылка некорректна\n"
    "• Платформа временно недоступна"
),
"video_download_error": (
    "Ошибка при скачивании видео.\n"
    "Попробуй:\n"
    "• Выбрать другое качество\n"
    "• Повторить позже"
),
"video_too_large": (
    "Видео слишком большое ({size_mb}MB, лимит {limit_mb}MB).\n"
    "Попробуй выбрать более низкое качество."
),
"video_no_formats": "Нет доступных форматов видео (144p–720p).",
```

### Регистрация роутера: `bot.py`

```python
from claude_bot.handlers import ..., video

# Между document и text (text — catch-all, должен быть последним)
dp.include_router(video.router)
dp.include_router(text.router)
```

---

## Порядок реализации

| # | Действие | Файлы |
|---|----------|-------|
| 1 | Docker-compose для Local Bot API | `docker-compose.yml` |
| 2 | Настройки Local Bot API | `config.py`, `.env.example`, `bot.py` |
| 3 | Добавить yt-dlp | `pyproject.toml` → `uv sync` |
| 4 | Константы и ошибки | `constants.py`, `errors.py` |
| 5 | Сервис видео | `services/video.py` (новый) |
| 6 | Клавиатура | `keyboards.py` |
| 7 | Хендлер видео | `handlers/video.py` (новый) |
| 8 | Регистрация роутера | `bot.py` |
| 9 | CHANGELOG | `CHANGELOG.md` |

---

## Ограничения

- Только публичные видео (без авторизации на платформах)
- VK может требовать cookie для некоторых видео — ограничение yt-dlp
- Без Local Bot API — лимит 50MB; с Local Bot API — 2GB
- Таймаут скачивания — 5 минут

---

## Проверка

1. `docker-compose up -d telegram-bot-api` — контейнер Local Bot API запустился
2. `uv sync` — yt-dlp установлен
3. `uv run python -c "import yt_dlp; print(yt_dlp.version.__version__)"` — импорт работает
4. Отправить боту ссылку на YouTube видео → появляется клавиатура с качествами
5. Выбрать качество → видео скачивается и приходит в чат
6. Кнопка ❌ Отмена → сообщение удаляется
7. Невалидная ссылка → сообщение об ошибке
8. Видео > лимита → сообщение "слишком большое"
9. Проверить RuTube и VK Video ссылки
