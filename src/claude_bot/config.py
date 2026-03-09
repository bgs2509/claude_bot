"""Конфигурация бота через переменные окружения."""

import json
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки бота. Читаются из .env и переменных окружения."""

    telegram_bot_token: str
    projects_dir: Path = Path("/home/claude/projects")
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    tts_voice: str = "ru-RU-DmitryNeural"
    max_message_len: int = 4000
    default_provider: str = "claude"
    enabled_providers: list[str] = ["claude", "codex"]
    claude_bin: str = "claude"
    codex_bin: str = "codex"
    claude_timeout: int = 600
    codex_timeout: int = 600
    codex_default_model: str = "gpt-5.4"
    codex_models: list[str] = [
        "gpt-5.3-codex",
        "gpt-5.4",
        "gpt-5.2-codex",
        "gpt-5.1-codex-max",
        "gpt-5.2",
        "gpt-5.1-codex-mini",
    ]
    codex_default_reasoning_effort: str = "xhigh"
    codex_reasoning_levels: list[str] = ["low", "medium", "high", "xhigh"]
    users: dict = {}

    # Disable automatic JSON decoding for env values so CSV strings like
    # ENABLED_PROVIDERS=claude,codex reach our validators as raw text.
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        enable_decoding=False,
    )

    @field_validator("users", mode="before")
    @classmethod
    def parse_users_json(cls, v: str | dict) -> dict:
        if isinstance(v, str):
            return json.loads(v) if v.strip() else {}
        return v

    @field_validator("enabled_providers", "codex_models", "codex_reasoning_levels", mode="before")
    @classmethod
    def parse_csv_list(cls, v: str | list[str]) -> list[str]:
        if isinstance(v, str):
            return [item.strip() for item in v.split(",") if item.strip()]
        return v
