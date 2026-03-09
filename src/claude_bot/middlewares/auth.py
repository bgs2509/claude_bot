"""Middleware авторизации: проверка доступа и пробрасывание зависимостей."""

from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import Message, TelegramObject

from claude_bot.config import Settings
from claude_bot.services.ai.manager import AIManager
from claude_bot.state import AppState


class AuthMiddleware(BaseMiddleware):
    """Проверяет доступ пользователя и пробрасывает settings/state в data."""

    def __init__(self, settings: Settings, state: AppState, ai_manager: AIManager) -> None:
        self.settings = settings
        self.state = state
        self.ai_manager = ai_manager

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Пробрасываем зависимости в data
        data["settings"] = self.settings
        data["state"] = self.state
        data["ai_manager"] = self.ai_manager

        # Проверяем доступ только для Message
        if isinstance(event, Message) and event.from_user:
            uid = event.from_user.id
            if not self._is_allowed(uid):
                await event.answer("⛔ Доступ запрещён. Обратитесь к администратору.")
                return None

            # Пробрасываем роль и конфиг пользователя
            user_cfg = self.settings.users.get(str(uid))
            data["user_config"] = user_cfg
            data["role"] = user_cfg.get("role", "readonly") if user_cfg else "readonly"

        return await handler(event, data)

    def _is_allowed(self, uid: int) -> bool:
        """Проверка доступа. Если USERS пуст — доступ всем (режим разработки)."""
        if not self.settings.users:
            return True
        return str(uid) in self.settings.users


def check_limit(uid: int, settings: Settings, state: AppState) -> bool:
    """Проверить дневной лимит сообщений. True = можно отправить."""
    today = date.today().isoformat()
    data = state.user_daily_count.get(uid, {"date": "", "count": 0})

    if data["date"] != today:
        data = {"date": today, "count": 0}

    # Всегда инкрементируем счётчик (для /usage и /stats)
    data["count"] += 1
    state.user_daily_count[uid] = data

    cfg = settings.users.get(str(uid))
    if not cfg:
        return True
    limit = cfg.get("limit", 0)
    if limit == 0:
        return True  # Безлимит

    return data["count"] <= limit
