"""Состояние бота (in-memory)."""

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class PendingUpload:
    """Файл, ожидающий решения пользователя по коллизии."""

    tmp_path: str
    target_dir: str
    filename: str
    is_binary: bool
    caption: str
    chat_id: int
    ocr_text: str | None = None


@dataclass
class AppState:
    """Общее состояние приложения. Передаётся через data["app_state"] в хендлерах."""

    # uid → session_id
    user_sessions: dict[int, str] = field(default_factory=dict)
    # uid → короткое имя модели (haiku/sonnet/opus)
    user_models: dict[int, str] = field(default_factory=dict)
    # uid → голосовой режим
    user_voice_mode: dict[int, bool] = field(default_factory=dict)
    # uid → {"date": "YYYY-MM-DD", "count": N}
    user_daily_count: dict[int, dict] = field(default_factory=dict)
    # uid → список timestamp последних запросов (для rate-limit)
    user_request_times: dict[int, list[float]] = field(default_factory=dict)
    # uid → активный процесс Claude
    active_processes: dict[int, asyncio.subprocess.Process] = field(default_factory=dict)

    # uid → файл, ожидающий решения по коллизии
    pending_uploads: dict[int, PendingUpload] = field(default_factory=dict)

    # Ленивая загрузка тяжёлых модулей
    whisper_model: Any = None
    tesseract_available: bool | None = None
