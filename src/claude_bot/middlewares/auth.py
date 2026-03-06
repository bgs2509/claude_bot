"""Middleware авторизации: проверка доступа и пробрасывание зависимостей."""

import time
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from claude_bot.config import Settings
from claude_bot.state import AppState

if __name__ != "__never__":
    from claude_bot.services.storage import SessionStorage


class AuthMiddleware(BaseMiddleware):
    """Проверяет доступ пользователя и пробрасывает settings/state/storage в data."""

    def __init__(
        self,
        settings: Settings,
        state: AppState,
        storage: "SessionStorage | None" = None,
    ) -> None:
        self.settings = settings
        self.state = state
        self.storage = storage

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["settings"] = self.settings
        data["state"] = self.state
        data["storage"] = self.storage

        # Получить from_user из Message или CallbackQuery
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            uid = user.id
            if not self._is_allowed(uid):
                if isinstance(event, CallbackQuery):
                    await event.answer("Доступ запрещён", show_alert=True)
                elif isinstance(event, Message):
                    await event.answer("Доступ запрещён. Обратитесь к администратору.")
                return None

            user_cfg = self.settings.users.get(str(uid))
            data["user_config"] = user_cfg
            data["role"] = user_cfg.get("role", "readonly") if user_cfg else "readonly"

        return await handler(event, data)

    def _is_allowed(self, uid: int) -> bool:
        """Проверка доступа. Если USERS пуст — доступ всем (режим разработки)."""
        if not self.settings.users:
            return True
        return str(uid) in self.settings.users


def check_rate_limit(uid: int, settings: Settings, state: AppState) -> float:
    """Проверить rate-limit для роли user. Возвращает 0 если можно, иначе секунды ожидания."""
    cfg = settings.users.get(str(uid))
    if not cfg:
        return 0.0
    if cfg.get("role") != "user":
        return 0.0  # Rate-limit только для роли user

    now = time.time()
    window = 60.0
    max_requests = 2

    times = state.user_request_times.get(uid, [])
    # Оставить только запросы в пределах окна
    times = [t for t in times if now - t < window]

    if len(times) >= max_requests:
        wait = window - (now - times[0])
        state.user_request_times[uid] = times
        return max(wait, 0.1)

    times.append(now)
    state.user_request_times[uid] = times
    return 0.0


def track_usage(uid: int, state: AppState) -> None:
    """Инкремент дневного счётчика для статистики (/usage, /stats)."""
    today = date.today().isoformat()
    data = state.user_daily_count.get(uid, {"date": "", "count": 0})
    if data["date"] != today:
        data = {"date": today, "count": 0}
    data["count"] += 1
    state.user_daily_count[uid] = data
