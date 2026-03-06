"""Сервис взаимодействия с Claude Code CLI."""

import asyncio
import json
import logging
import os
from pathlib import Path

from aiogram import types

from claude_bot.config import Settings
from claude_bot.state import AppState

log = logging.getLogger("claude-bot")


def get_project_dir(uid: int, settings: Settings, state: AppState) -> Path:
    """Рабочая директория проекта для пользователя."""
    project = state.user_projects.get(uid)
    if project:
        return settings.projects_dir / project
    return settings.projects_dir


async def run_claude(
    prompt: str, uid: int, settings: Settings, state: AppState
) -> str:
    """Запустить Claude Code CLI и получить результат."""
    cwd = get_project_dir(uid, settings, state)
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
        return f"⏰ Таймаут ({settings.claude_timeout // 60} мин). Используй /cancel для прерывания."
    finally:
        state.active_processes.pop(uid, None)

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
            state.user_sessions[uid] = sid
    except json.JSONDecodeError:
        result = raw

    return result


async def send_long(message: types.Message, text: str, max_len: int = 4000) -> None:
    """Отправка длинных сообщений с разбивкой."""
    if not text.strip():
        text = "(пустой ответ)"
    for i in range(0, len(text), max_len):
        await message.answer(text[i:i + max_len])
