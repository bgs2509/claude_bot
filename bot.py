"""
Claude Code Telegram Bot
Универсальный AI-ассистент: разработка, учёба, медиа, документация, аналитика.
"""

import asyncio
import json
import logging
import os
import subprocess
import tempfile
from datetime import datetime, date
from pathlib import Path

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import FSInputFile

# ─── Настройки ───────────────────────────────────────────────

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
PROJECTS_DIR = Path(os.getenv("PROJECTS_DIR", "/home/claude/projects"))
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
TTS_VOICE = os.getenv("TTS_VOICE", "ru-RU-DmitryNeural")
MAX_MESSAGE_LEN = 4000
CLAUDE_TIMEOUT = int(os.getenv("CLAUDE_TIMEOUT", "600"))  # 10 минут

# Пользователи: JSON строка из .env
# Формат: {"tg_id": {"role": "admin", "limit": 0, "name": "Имя"}}
USERS_CONFIG: dict = json.loads(os.getenv("USERS", "{}"))

# ─── Логирование ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("claude-bot")

# ─── Инициализация ───────────────────────────────────────────

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Состояние пользователей
user_sessions: dict[int, str] = {}           # uid → session_id
user_projects: dict[int, str] = {}           # uid → имя проекта
user_voice_mode: dict[int, bool] = {}        # uid → голосовой режим
user_daily_count: dict[int, dict] = {}       # uid → {"date": "YYYY-MM-DD", "count": N}
active_processes: dict[int, asyncio.subprocess.Process] = {}

# Ленивая загрузка тяжёлых модулей
_whisper_model = None
_tesseract_available = None


# ─── Утилиты ─────────────────────────────────────────────────

def get_user_config(uid: int) -> dict | None:
    """Получить конфиг пользователя по Telegram ID."""
    return USERS_CONFIG.get(str(uid))


def is_allowed(uid: int) -> bool:
    """Проверка доступа. Если USERS пуст — доступ всем (режим разработки)."""
    if not USERS_CONFIG:
        return True
    return str(uid) in USERS_CONFIG


def get_role(uid: int) -> str:
    """Получить роль пользователя."""
    cfg = get_user_config(uid)
    if not cfg:
        return "readonly"
    return cfg.get("role", "readonly")


def check_limit(uid: int) -> bool:
    """Проверить дневной лимит сообщений. True = можно отправить."""
    cfg = get_user_config(uid)
    if not cfg:
        return True
    limit = cfg.get("limit", 0)
    if limit == 0:
        return True  # Безлимит

    today = date.today().isoformat()
    data = user_daily_count.get(uid, {"date": "", "count": 0})

    if data["date"] != today:
        data = {"date": today, "count": 0}

    if data["count"] >= limit:
        return False

    data["count"] += 1
    user_daily_count[uid] = data
    return True


def get_project_dir(uid: int) -> Path:
    """Рабочая директория проекта для пользователя."""
    project = user_projects.get(uid)
    if project:
        return PROJECTS_DIR / project
    return PROJECTS_DIR


def get_whisper_model():
    """Ленивая загрузка Whisper модели."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            _whisper_model = WhisperModel(WHISPER_MODEL, compute_type="int8")
            log.info(f"Whisper модель '{WHISPER_MODEL}' загружена")
        except ImportError:
            log.warning("faster-whisper не установлен, STT недоступен")
            return None
    return _whisper_model


def is_tesseract_available() -> bool:
    """Проверить доступность tesseract."""
    global _tesseract_available
    if _tesseract_available is None:
        try:
            subprocess.run(["tesseract", "--version"], capture_output=True, check=True)
            _tesseract_available = True
        except (FileNotFoundError, subprocess.CalledProcessError):
            _tesseract_available = False
    return _tesseract_available


async def send_long(message: types.Message, text: str):
    """Отправка длинных сообщений с разбивкой."""
    if not text.strip():
        text = "(пустой ответ)"
    chunks = []
    for i in range(0, len(text), MAX_MESSAGE_LEN):
        chunks.append(text[i:i + MAX_MESSAGE_LEN])
    for chunk in chunks:
        await message.answer(chunk)


async def transcribe_voice(file_path: str) -> str | None:
    """Транскрибировать голосовое сообщение в текст."""
    model = get_whisper_model()
    if model is None:
        return None

    # Конвертировать ogg → wav через ffmpeg
    wav_path = file_path.replace(".ogg", ".wav")
    proc = await asyncio.create_subprocess_exec(
        "ffmpeg", "-i", file_path, "-ar", "16000", "-ac", "1", wav_path,
        "-y", "-loglevel", "error",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()

    if proc.returncode != 0:
        return None

    # Транскрибация
    segments, _ = model.transcribe(wav_path, language="ru")
    text = " ".join(s.text for s in segments).strip()

    # Удалить временные файлы
    for p in (file_path, wav_path):
        try:
            os.unlink(p)
        except OSError:
            pass

    return text


async def synthesize_speech(text: str) -> str | None:
    """Синтезировать речь из текста через edge-tts."""
    try:
        import edge_tts
    except ImportError:
        return None

    # Ограничить длину текста для TTS (edge-tts имеет лимит)
    if len(text) > 3000:
        text = text[:3000] + "..."

    output_path = tempfile.mktemp(suffix=".mp3")
    communicate = edge_tts.Communicate(text, TTS_VOICE)
    await communicate.save(output_path)
    return output_path


async def ocr_image(file_path: str) -> str:
    """Извлечь текст из изображения через tesseract."""
    if not is_tesseract_available():
        return "(tesseract не установлен — OCR недоступен)"

    try:
        from PIL import Image
        import pytesseract
        image = Image.open(file_path)
        text = pytesseract.image_to_string(image, lang="rus+eng")
        return text.strip() if text.strip() else "(текст на фото не распознан)"
    except Exception as e:
        return f"(ошибка OCR: {e})"
    finally:
        try:
            os.unlink(file_path)
        except OSError:
            pass


async def run_claude(prompt: str, uid: int) -> str:
    """Запустить Claude Code CLI и получить результат."""
    cwd = get_project_dir(uid)
    cwd.mkdir(parents=True, exist_ok=True)

    cmd = [
        "claude", "-p", prompt, "--output-format", "json",
        "--append-system-prompt",
        "ФОРМАТ ОТВЕТА: "
        "НИКОГДА не используй таблицы. "
        "Вместо таблиц используй многоуровневые маркированные или нумерованные списки. "
        "Форматирование: только plain text, списки и переносы строк.",
    ]

    # Продолжить сессию если есть
    session_id = user_sessions.get(uid)
    if session_id:
        cmd += ["--resume", session_id]

    # Права: admin и user — полный доступ, readonly — только чтение
    role = get_role(uid)
    if role in ("admin", "user"):
        cmd += ["--dangerously-skip-permissions"]

    env = os.environ.copy()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
        env=env,
    )
    active_processes[uid] = proc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=CLAUDE_TIMEOUT
        )
    except asyncio.TimeoutError:
        proc.kill()
        return f"⏰ Таймаут ({CLAUDE_TIMEOUT // 60} мин). Используй /cancel для прерывания."
    finally:
        active_processes.pop(uid, None)

    raw = stdout.decode().strip()
    if not raw:
        err = stderr.decode().strip()
        return err if err else "(пустой ответ)"

    # Извлечь текст и session_id из JSON
    try:
        data = json.loads(raw)
        result = data.get("result", raw)
        sid = data.get("session_id")
        if sid:
            user_sessions[uid] = sid
    except json.JSONDecodeError:
        result = raw

    return result


# ─── Обработчики команд ─────────────────────────────────────

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if not is_allowed(message.from_user.id):
        await message.answer("⛔ Доступ запрещён. Обратитесь к администратору.")
        return

    role = get_role(message.from_user.id)
    await message.answer(
        f"Claude Code Bot\n\n"
        f"Роль: {role}\n"
        f"Проект: {user_projects.get(message.from_user.id, '(по умолчанию)')}\n\n"
        f"Просто отправь текст, голосовое или фото.\n\n"
        f"Команды:\n"
        f"/new — новая сессия\n"
        f"/cancel — отменить запрос\n"
        f"/session — ID сессии\n"
        f"/project — список проектов\n"
        f"/project <имя> — переключить проект\n"
        f"/voice — вкл/выкл голосовые ответы\n"
        f"/stats — статистика (admin)"
    )


@dp.message(Command("new"))
async def cmd_new(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    uid = message.from_user.id
    user_sessions.pop(uid, None)
    await message.answer("Сессия сброшена. Следующее сообщение начнёт новую.")


@dp.message(Command("cancel"))
async def cmd_cancel(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    uid = message.from_user.id
    proc = active_processes.pop(uid, None)
    if proc:
        proc.kill()
        await message.answer("Запрос отменён.")
    else:
        await message.answer("Нет активного запроса.")


@dp.message(Command("session"))
async def cmd_session(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    sid = user_sessions.get(message.from_user.id, "нет сессии")
    await message.answer(f"Session ID: {sid}")


@dp.message(Command("project"))
async def cmd_project(message: types.Message, command: CommandObject):
    if not is_allowed(message.from_user.id):
        return
    uid = message.from_user.id
    args = command.args

    if not args:
        # Показать список проектов
        if not PROJECTS_DIR.exists():
            await message.answer(f"Директория проектов не найдена: {PROJECTS_DIR}")
            return
        projects = sorted(
            d.name for d in PROJECTS_DIR.iterdir() if d.is_dir()
        )
        if not projects:
            await message.answer(f"Нет проектов в {PROJECTS_DIR}")
            return

        current = user_projects.get(uid, "")
        lines = []
        for p in projects:
            marker = " ◀" if p == current else ""
            lines.append(f"  {p}{marker}")
        await message.answer(
            f"Проекты ({PROJECTS_DIR}):\n" + "\n".join(lines) +
            "\n\nПереключить: /project <имя>"
        )
        return

    # Переключить проект
    project_name = args.strip()
    project_path = PROJECTS_DIR / project_name
    if not project_path.exists():
        # Создать новый проект
        project_path.mkdir(parents=True, exist_ok=True)
        await message.answer(f"Создан и переключён на проект: {project_name}")
    else:
        await message.answer(f"Переключён на проект: {project_name}")

    user_projects[uid] = project_name
    # Сбросить сессию при смене проекта
    user_sessions.pop(uid, None)


@dp.message(Command("voice"))
async def cmd_voice(message: types.Message):
    if not is_allowed(message.from_user.id):
        return
    uid = message.from_user.id
    current = user_voice_mode.get(uid, False)
    user_voice_mode[uid] = not current
    status = "включён" if not current else "выключен"
    await message.answer(f"Голосовой режим {status}")


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    uid = message.from_user.id
    if not is_allowed(uid):
        return
    if get_role(uid) != "admin":
        await message.answer("Только для admin.")
        return

    lines = ["Статистика:\n"]
    for user_id_str, cfg in USERS_CONFIG.items():
        name = cfg.get("name", user_id_str)
        role = cfg.get("role", "?")
        count_data = user_daily_count.get(int(user_id_str), {})
        today_count = count_data.get("count", 0) if count_data.get("date") == date.today().isoformat() else 0
        limit = cfg.get("limit", 0)
        limit_str = f"{today_count}/{limit}" if limit else f"{today_count}/∞"
        lines.append(f"  {name} ({role}): {limit_str} сегодня")

    await message.answer("\n".join(lines))


# ─── Обработчики сообщений ───────────────────────────────────

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    """Обработка голосовых сообщений."""
    uid = message.from_user.id
    if not is_allowed(uid):
        return
    if not check_limit(uid):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    waiting = await message.answer("🎤 Транскрибирую...")

    # Скачать голосовое сообщение
    voice = message.voice
    file = await bot.get_file(voice.file_id)
    ogg_path = tempfile.mktemp(suffix=".ogg")
    await bot.download_file(file.file_path, ogg_path)

    # Транскрибировать
    text = await transcribe_voice(ogg_path)
    if not text:
        await waiting.edit_text("Не удалось распознать голос. Отправь текстом.")
        return

    await waiting.edit_text(f"🎤 Распознано: {text}\n\n⏳ Claude думает...")

    # Отправить в Claude
    result = await run_claude(text, uid)

    # Отправить результат
    await send_long(message, result)

    # Голосовой ответ (если включён)
    if user_voice_mode.get(uid, False):
        mp3_path = await synthesize_speech(result)
        if mp3_path:
            audio = FSInputFile(mp3_path)
            await message.answer_voice(audio)
            try:
                os.unlink(mp3_path)
            except OSError:
                pass

    try:
        await waiting.delete()
    except Exception:
        pass


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    """Обработка фотографий."""
    uid = message.from_user.id
    if not is_allowed(uid):
        return
    if not check_limit(uid):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    waiting = await message.answer("📷 Обрабатываю фото...")

    # Скачать фото (берём наибольшее разрешение)
    photo = message.photo[-1]
    file = await bot.get_file(photo.file_id)
    img_path = tempfile.mktemp(suffix=".jpg")
    await bot.download_file(file.file_path, img_path)

    # OCR
    ocr_text = await ocr_image(img_path)

    # Формируем промпт
    caption = message.caption or "Проанализируй это изображение"
    prompt = f"Пользователь отправил фото. OCR распознал текст:\n\n```\n{ocr_text}\n```\n\nЗадача пользователя: {caption}"

    await waiting.edit_text("⏳ Claude думает...")

    result = await run_claude(prompt, uid)
    await send_long(message, result)

    try:
        await waiting.delete()
    except Exception:
        pass


@dp.message(F.document)
async def handle_document(message: types.Message):
    """Обработка документов (текстовые файлы)."""
    uid = message.from_user.id
    if not is_allowed(uid):
        return
    if not check_limit(uid):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    doc = message.document
    # Обрабатывать только текстовые файлы до 1MB
    if doc.file_size > 1_000_000:
        await message.answer("Файл слишком большой (макс 1MB).")
        return

    waiting = await message.answer("📄 Читаю файл...")

    file = await bot.get_file(doc.file_id)
    tmp_path = tempfile.mktemp(suffix=f"_{doc.file_name}")
    await bot.download_file(file.file_path, tmp_path)

    try:
        with open(tmp_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
    except Exception as e:
        await waiting.edit_text(f"Не удалось прочитать файл: {e}")
        return
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    caption = message.caption or "Проанализируй этот файл"
    prompt = f"Пользователь отправил файл `{doc.file_name}`:\n\n```\n{content[:10000]}\n```\n\nЗадача: {caption}"

    await waiting.edit_text("⏳ Claude думает...")

    result = await run_claude(prompt, uid)
    await send_long(message, result)

    try:
        await waiting.delete()
    except Exception:
        pass


@dp.message(F.text)
async def handle_text(message: types.Message):
    """Обработка текстовых сообщений."""
    uid = message.from_user.id
    if not is_allowed(uid):
        return
    if not check_limit(uid):
        await message.answer("Дневной лимит сообщений исчерпан.")
        return

    prompt = message.text
    if not prompt:
        return

    waiting = await message.answer("⏳ Claude думает...")

    result = await run_claude(prompt, uid)
    await send_long(message, result)

    # Голосовой ответ (если включён)
    if user_voice_mode.get(uid, False):
        mp3_path = await synthesize_speech(result)
        if mp3_path:
            audio = FSInputFile(mp3_path)
            await message.answer_voice(audio)
            try:
                os.unlink(mp3_path)
            except OSError:
                pass

    try:
        await waiting.delete()
    except Exception:
        pass


# ─── Запуск ──────────────────────────────────────────────────

async def main():
    log.info("Claude Code Telegram Bot запущен")
    log.info(f"Проекты: {PROJECTS_DIR}")
    log.info(f"Пользователей: {len(USERS_CONFIG) or 'без ограничений'}")
    log.info(f"Whisper модель: {WHISPER_MODEL}")
    log.info(f"TTS голос: {TTS_VOICE}")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
