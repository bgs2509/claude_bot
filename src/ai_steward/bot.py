"""Фабрики для создания бота и диспетчера."""

from __future__ import annotations

from typing import TYPE_CHECKING

from aiogram import Bot, Dispatcher

from ai_steward.config import Settings
from ai_steward.handlers import commands, document, photo, project_switch, text, upload, voice
from ai_steward.middlewares.auth import AuthMiddleware
from ai_steward.middlewares.error import ErrorMiddleware
from ai_steward.middlewares.observability import ObservabilityMiddleware
from ai_steward.services.storage import SessionStorage
from ai_steward.state import AppState

if TYPE_CHECKING:
    from ai_steward.services.analytics import EventLogger


def create_bot(settings: Settings) -> Bot:
    """Создать экземпляр бота."""
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher(
    settings: Settings,
    state: AppState,
    storage: SessionStorage | None = None,
    *,
    event_logger: EventLogger | None = None,
) -> Dispatcher:
    """Создать диспетчер с зарегистрированными роутерами и middleware."""
    dp = Dispatcher()

    # Outer middleware — запускается ДО фильтров (порядок: error → auth → obs)
    error_mw = ErrorMiddleware()
    dp.message.outer_middleware(error_mw)
    dp.callback_query.outer_middleware(error_mw)

    auth = AuthMiddleware(settings, state, storage)
    dp.message.outer_middleware(auth)
    dp.callback_query.outer_middleware(auth)

    obs = ObservabilityMiddleware(event_logger)
    dp.message.outer_middleware(obs)
    dp.callback_query.outer_middleware(obs)

    # Роутеры (порядок важен: project_switch перед text, text последним — ловит всё)
    dp.include_router(commands.router)
    dp.include_router(project_switch.router)
    dp.include_router(upload.router)
    dp.include_router(voice.router)
    dp.include_router(photo.router)
    dp.include_router(document.router)
    dp.include_router(text.router)

    return dp
