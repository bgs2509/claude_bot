"""Сервис взаимодействия с Claude Code CLI."""

import asyncio
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from aiogram import types
from aiogram.types import FSInputFile

from claude_bot.config import Settings
from claude_bot.state import AppState

log = logging.getLogger("claude-bot")

MEDIA_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".pdf", ".csv", ".xlsx", ".mp3", ".mp4",
}


@dataclass
class ClaudeResponse:
    """Результат выполнения Claude Code. Общий интерфейс для бота и веба."""
    text: str
    session_id: str | None = None
    files: list[Path] = field(default_factory=list)


def get_project_dir(uid: int, settings: Settings, state: AppState) -> Path:
    """Рабочая директория проекта для пользователя."""
    project = state.user_projects.get(uid)
    if project:
        return settings.projects_dir / project
    return settings.projects_dir


def _snapshot_media(cwd: Path) -> set[Path]:
    """Снимок медиа-файлов в корне директории (без рекурсии)."""
    return {
        p for p in cwd.iterdir()
        if p.is_file() and p.suffix.lower() in MEDIA_EXTENSIONS
    }


def _collect_output_files(cwd: Path, before: set[Path]) -> list[Path]:
    """Собрать файлы из _output/ и новые медиа из корня."""
    files: list[Path] = []
    output_dir = cwd / "_output"
    if output_dir.exists():
        files.extend(p for p in output_dir.iterdir() if p.is_file())
    # Fallback: новые медиа-файлы в корне
    after = _snapshot_media(cwd)
    files.extend(after - before)
    return files


async def run_claude(
    prompt: str, uid: int, settings: Settings, state: AppState
) -> ClaudeResponse:
    """Запустить Claude Code CLI и получить результат."""
    cwd = get_project_dir(uid, settings, state)
    cwd.mkdir(parents=True, exist_ok=True)

    # Подготовка _output/ и снимок медиа
    output_dir = cwd / "_output"
    output_dir.mkdir(exist_ok=True)
    # Очистить _output/ от предыдущих запусков
    for old_file in output_dir.iterdir():
        if old_file.is_file():
            old_file.unlink()
    media_before = _snapshot_media(cwd)

    cmd = [
        "claude", "-p", prompt, "--output-format", "json",
        "--append-system-prompt",
        "ФОРМАТ ОТВЕТА: "
        "НИКОГДА не используй таблицы. "
        "Вместо таблиц используй многоуровневые маркированные или нумерованные списки. "
        "Форматирование: только plain text, списки и переносы строк. "
        "Все создаваемые файлы (скриншоты, изображения, CSV, и т.д.) "
        "сохраняй в папку _output/ в текущей директории.",
    ]

    # Продолжить сессию если есть
    session_id = state.user_sessions.get(uid)
    if session_id:
        cmd += ["--resume", session_id]

    # Права: admin и user — полный доступ, readonly — только чтение
    cfg = settings.users.get(str(uid))
    role = cfg.get("role", "readonly") if cfg else "readonly"
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
    state.active_processes[uid] = proc

    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=settings.claude_timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        return ClaudeResponse(
            text=f"⏰ Таймаут ({settings.claude_timeout // 60} мин). Используй /cancel для прерывания."
        )
    finally:
        state.active_processes.pop(uid, None)

    raw = stdout.decode().strip()
    if not raw:
        err = stderr.decode().strip()
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
            state.user_sessions[uid] = sid
    except json.JSONDecodeError:
        pass

    # Собрать файлы
    collected_files = _collect_output_files(cwd, media_before)

    return ClaudeResponse(text=result_text, session_id=sid, files=collected_files)


async def send_long(message: types.Message, text: str, max_len: int = 4000) -> None:
    """Отправка ответа. Если > max_len — первый чанк + .md файл."""
    if not text.strip():
        text = "(пустой ответ)"

    if len(text) <= max_len:
        await message.answer(text)
        return

    # Первый чанк + файл с полным ответом
    preview = text[:max_len]
    await message.answer(preview)

    md_path = tempfile.mktemp(suffix=".md")
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(text)
    doc = FSInputFile(md_path, filename="response.md")
    await message.answer_document(doc, caption="Полный ответ в файле")
    os.unlink(md_path)
