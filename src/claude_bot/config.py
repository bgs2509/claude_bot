"""Конфигурация бота через переменные окружения."""

import json
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки бота. Читаются из .env и переменных окружения."""

    telegram_bot_token: str
    projects_dir: Path = Path("/home/claude/projects")
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    tts_voice: str = "ru-RU-DmitryNeural"
    max_message_len: int = 4000
    claude_timeout: int = 600
    users: dict = {}

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("users", mode="before")
    @classmethod
    def parse_users_json(cls, v: str | dict) -> dict:
        if isinstance(v, str):
            return json.loads(v) if v.strip() else {}
        return v
