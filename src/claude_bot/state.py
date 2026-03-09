"""Состояние бота (in-memory)."""

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UserAIState:
    """AI-настройки конкретного пользователя."""

    provider: str
    model: str | None = None
    reasoning_effort: str | None = None
    session_id: str | None = None


@dataclass
class AppState:
    """Общее состояние приложения. Передаётся через data["state"] в хендлерах."""

    # uid → выбранный provider/model/session
    user_ai: dict[int, UserAIState] = field(default_factory=dict)
    # uid → голосовой режим
    user_voice_mode: dict[int, bool] = field(default_factory=dict)
    # uid → {"date": "YYYY-MM-DD", "count": N}
    user_daily_count: dict[int, dict] = field(default_factory=dict)
    # uid → активный процесс AI-провайдера
    active_processes: dict[int, asyncio.subprocess.Process] = field(default_factory=dict)

    # Ленивая загрузка тяжёлых модулей
    whisper_model: Any = None
    tesseract_available: bool | None = None

    def get_or_create_user_ai(self, uid: int, default_provider: str) -> UserAIState:
        """Получить AI-профиль пользователя или создать его с дефолтным провайдером."""

        profile = self.user_ai.get(uid)
        if profile is None:
            profile = UserAIState(provider=default_provider)
            self.user_ai[uid] = profile
        return profile
