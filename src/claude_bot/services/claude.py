"""Сервис взаимодействия с Claude Code CLI."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from aiogram import types
from aiogram.types import FSInputFile

from claude_bot.config import Settings, get_user_projects_dir
from claude_bot.errors import get_user_message
from claude_bot.services.format_telegram import markdown_to_telegram_html
from claude_bot.state import AppState

if TYPE_CHECKING:
    from claude_bot.services.storage import SessionStorage

log = logging.getLogger("claude-bot")

MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".csv", ".xlsx", ".mp3", ".mp4",
}

# Маппинг коротких имён → полных model ID
MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}


@dataclass
class ClaudeResponse:
    """Результат выполнения Claude Code. Общий интерфейс для бота и веба."""
    text: str
    session_id: str | None = None
    files: list[Path] = field(default_factory=list)


_TITLE_RE = re.compile(r"\[TITLE:\s*(.+?)\]\s*$", re.IGNORECASE)


def _extract_title(text: str) -> tuple[str, str | None]:
    """Извлечь [TITLE: ...] из конца текста. Возвращает (текст_без_title, title)."""
    match = _TITLE_RE.search(text)
    if match:
        return text[:match.start()].rstrip(), match.group(1).strip()
    return text, None


def get_project_dir(
    settings: Settings,
    storage: SessionStorage | None = None,
    uid: int | None = None,
) -> Path:
    """Рабочая директория для Claude. Per-user projects_dir + active_project."""
    if uid is None:
        raise ValueError("uid обязателен для определения рабочей директории")
    base = get_user_projects_dir(settings, uid)
    if storage:
        user = storage.get_user(uid)
        if user.active_project:
            return base / user.active_project
    return base


def _snapshot_media(cwd: Path) -> set[Path]:
    """Снимок медиа-файлов в корне директории (без рекурсии)."""
    return {
        p for p in cwd.iterdir()
        if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
    }


def _snapshot_output(cwd: Path) -> set[Path]:
    """Снимок файлов в _output/."""
    output_dir = cwd / "_output"
    if not output_dir.exists():
        return set()
    return {p for p in output_dir.iterdir() if p.is_file()}


def _collect_output_files(
    cwd: Path, media_before: set[Path], output_before: set[Path],
) -> list[Path]:
    """Собрать НОВЫЕ файлы из _output/ и новые медиа из корня."""
    files: list[Path] = []
    output_dir = cwd / "_output"
    if output_dir.exists():
        after = {p for p in output_dir.iterdir() if p.is_file()}
        files.extend(after - output_before)
    # Fallback: новые медиа-файлы в корне
    media_after = _snapshot_media(cwd)
    files.extend(media_after - media_before)
    return files


async def run_claude(
    prompt: str,
    uid: int,
    settings: Settings,
    app_state: AppState,
    storage: SessionStorage | None = None,
    *,
    _retry: bool = False,
) -> ClaudeResponse:
    """Запустить Claude Code CLI и получить результат."""
    cwd = get_project_dir(settings, storage, uid)
    cwd.mkdir(parents=True, exist_ok=True)

    # Подготовка _output/ и снимки для отслеживания новых файлов
    output_dir = cwd / "_output"
    output_dir.mkdir(exist_ok=True)
    output_before = _snapshot_output(cwd)
    media_before = _snapshot_media(cwd)

    cmd = [
        "claude", "-p", prompt, "--output-format", "json",
        "--append-system-prompt",
        "ФОРМАТ ОТВЕТА: "
        "НИКОГДА не используй таблицы. "
        "Вместо таблиц используй маркированные или нумерованные списки. "
        "Форматирование: plain text, списки, переносы строк. "
        "Файлы сохраняй в _output/ с именами в формате YYYYMMDD_HHMMSS_краткое_описание.расширение "
        "(например: 20260307_180000_анализ_продаж.csv). "
        "Пользователь общается через Telegram-бот. "
        "Он может просить выполнить bash-команды (cd, ls, mkdir, git и любые другие) — выполняй их. "
        "При смене директории сообщай текущий путь. "
        "Если тема разговора изменилась или расширилась, добавь в самом конце ответа "
        "[TITLE: три слова описывающие весь диалог целиком]. "
        "Если тема прежняя — не добавляй TITLE.",
    ]

    # Модель: из конфига юзера, для user — принудительно из конфига
    user_cfg = settings.users.get(str(uid))
    user_role = user_cfg.get("role", "readonly") if user_cfg else "readonly"
    config_model = user_cfg.get("model") if user_cfg else None

    if user_role == "user" and config_model:
        # Роль user — всегда модель из конфига, нельзя менять
        model_name = config_model
    elif config_model:
        # Admin — конфиг как дефолт, можно переопределить через /model
        model_name = app_state.user_models.get(uid, config_model)
    else:
        model_name = app_state.user_models.get(uid, "sonnet")

    model_id = MODELS.get(model_name, MODELS["sonnet"])
    cmd += ["--model", model_id]

    log.info("Claude CLI: model=%s, cwd=%s", model_name, cwd)

    # Продолжить сессию если есть
    session_id = None
    if storage:
        session_id = storage.get_active_session_id(uid)
    if not session_id:
        session_id = app_state.user_sessions.get(uid)
    if session_id:
        cmd += ["--resume", session_id]

    # Права: admin и user — полный доступ, readonly — только чтение
    if user_role in ("admin", "user"):
        cmd += ["--dangerously-skip-permissions"]

    env = os.environ.copy()

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        cwd=str(cwd),
        env=env,
    )
    app_state.active_processes[uid] = proc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=settings.claude_timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        return ClaudeResponse(text=get_user_message("claude_timeout"))
    finally:
        app_state.active_processes.pop(uid, None)

    raw = stdout.decode().strip()
    log.info("Claude CLI: exit=%d, stdout=%d bytes", proc.returncode or 0, len(raw))

    if not raw:
        err = stderr.decode().strip()
        # Auto-retry при невалидной сессии
        if not _retry and session_id and "No conversation found" in err:
            log.warning("Сессия %s невалидна, retry без --resume", session_id)
            app_state.user_sessions.pop(uid, None)
            if storage:
                await storage.create_new_session(uid)
            return await run_claude(
                prompt, uid, settings, app_state, storage=storage, _retry=True,
            )
        text = err if err else "(пустой ответ)"
        return ClaudeResponse(text=text)

    # Извлечь текст и session_id из JSON
    result_text = raw
    sid = None
    try:
        data = json.loads(raw)
        result_text = data.get("result", raw)
        sid = data.get("session_id")
        if sid:
            app_state.user_sessions[uid] = sid
    except json.JSONDecodeError:
        pass

    # Парсинг [TITLE:] и сохранение в storage
    title: str | None = None
    result_text, title = _extract_title(result_text)
    if sid and storage:
        # Fallback: первые 3 слова промпта
        session_name = title or " ".join(prompt.split()[:3])
        await storage.save_session(uid, sid, name=session_name if title else None)
        if title:
            await storage.update_session_name(uid, sid, title)

    # Собрать файлы
    collected_files = _collect_output_files(cwd, media_before, output_before)

    return ClaudeResponse(text=result_text, session_id=sid, files=collected_files)


async def _send_html_or_plain(message: types.Message, text: str) -> None:
    """Отправить сообщение как HTML, при ошибке — plain text."""
    formatted = markdown_to_telegram_html(text)
    try:
        await message.answer(formatted, parse_mode="HTML")
    except Exception:
        await message.answer(text)


async def send_long(message: types.Message, text: str, max_len: int = 4000) -> None:
    """Отправка ответа. Если > max_len — первый чанк + .md файл."""
    if not text.strip():
        text = "(пустой ответ)"

    if len(text) <= max_len:
        await _send_html_or_plain(message, text)
        return

    # Первый чанк + файл с полным ответом
    preview = text[:max_len]
    await _send_html_or_plain(message, preview)

    md_path = tempfile.mktemp(suffix=".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(text)
    doc = FSInputFile(md_path, filename="response.md")
    await message.answer_document(doc, caption="Полный ответ в файле")
    os.unlink(md_path)
