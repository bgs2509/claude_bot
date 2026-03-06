"""Состояние бота (in-memory)."""

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AppState:
    """Общее состояние приложения. Передаётся через data["state"] в хендлерах."""

    # uid → session_id
    user_sessions: dict[int, str] = field(default_factory=dict)
    # uid → короткое имя модели (haiku/sonnet/opus)
    user_models: dict[int, str] = field(default_factory=dict)
    # uid → голосовой режим
    user_voice_mode: dict[int, bool] = field(default_factory=dict)
    # uid → {"date": "YYYY-MM-DD", "count": N}
    user_daily_count: dict[int, dict] = field(default_factory=dict)
    # uid → активный процесс Claude
    active_processes: dict[int, asyncio.subprocess.Process] = field(default_factory=dict)

    # Ленивая загрузка тяжёлых модулей
    whisper_model: Any = None
    tesseract_available: bool | None = None
