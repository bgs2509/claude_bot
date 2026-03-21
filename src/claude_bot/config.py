"""Конфигурация бота через переменные окружения."""

import json
from pathlib import Path

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Настройки бота. Читаются из .env и переменных окружения."""

    telegram_bot_token: str
    sessions_file: Path = Path("data/sessions.json")
    whisper_model: str = "base"
    whisper_device: str = "cpu"
    tts_voice: str = "ru-RU-DmitryNeural"
    max_message_len: int = 4000
    claude_timeout: int = 600
    max_upload_size: int = 20_971_520  # 20MB
    users: dict = {}
    users_file: Path = Path("data/users.json")

    # Логирование
    log_file: Path = Path("data/bot.log")
    log_max_bytes: int = 10_485_760  # 10 MB
    log_backup_count: int = 5

    # Sentry (пустая строка = отключено)
    sentry_dsn: str = ""

    # Аналитика
    analytics_db: Path = Path("data/analytics.db")
    analytics_retention_days: int = 90

    # Уведомления (legacy-имена для обратной совместимости .env)
    notify_scan_interval: int = 60  # секунды между проверками
    notify_timezone: str = "Europe/Moscow"  # часовой пояс

    # Планировщик — дайджесты (HH:MM, пустая строка = выкл)
    plan_morning_time: str = "08:00"
    plan_evening_time: str = "22:00"

    model_config = {"env_file": ".env", "extra": "ignore"}

    @field_validator("users", mode="before")
    @classmethod
    def parse_users_json(cls, v: str | dict) -> dict:
        if isinstance(v, str):
            return json.loads(v) if v.strip() else {}
        return v

    @model_validator(mode="after")
    def load_users_from_file(self) -> "Settings":
        """Загрузить пользователей из JSON-файла, если USERS пуст."""
        if not self.users and self.users_file.exists():
            self.users = json.loads(self.users_file.read_text(encoding="utf-8"))
        return self

    @model_validator(mode="after")
    def validate_users_projects_dir(self) -> "Settings":
        """Проверить что у каждого юзера указан projects_dir."""
        for uid_str, cfg in self.users.items():
            if not cfg.get("projects_dir"):
                raise ValueError(
                    f"Пользователь {uid_str}: отсутствует обязательное поле 'projects_dir'"
                )
        return self


def get_user_projects_dir(settings: Settings, uid: int) -> Path:
    """Директория проектов конкретного пользователя."""
    user_cfg = settings.users.get(str(uid))
    if not user_cfg or not user_cfg.get("projects_dir"):
        raise ValueError(f"Пользователь {uid} не найден в конфиге или не указан projects_dir")
    return Path(user_cfg["projects_dir"])
