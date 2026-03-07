"""Фабрики для создания бота и диспетчера."""

from aiogram import Bot, Dispatcher

from claude_bot.config import Settings
from claude_bot.handlers import commands, document, photo, text, voice
from claude_bot.handlers.menu import router as menu_router
from claude_bot.middlewares.auth import AuthMiddleware
from claude_bot.middlewares.error import ErrorMiddleware
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState


def create_bot(settings: Settings) -> Bot:
    """Создать экземпляр бота."""
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher(
    settings: Settings,
    state: AppState,
    storage: SessionStorage | None = None,
) -> Dispatcher:
    """Создать диспетчер с зарегистрированными роутерами и middleware."""
    dp = Dispatcher()

    # ErrorMiddleware первым — ловит все необработанные исключения
    error_mw = ErrorMiddleware()
    dp.message.middleware(error_mw)
    dp.callback_query.middleware(error_mw)

    # AuthMiddleware вторым — авторизация и контекст
    auth = AuthMiddleware(settings, state, storage)
    dp.message.middleware(auth)
    dp.callback_query.middleware(auth)

    # Роутеры (порядок важен: menu до text, text последним — ловит всё)
    dp.include_router(commands.router)
    dp.include_router(menu_router)
    dp.include_router(voice.router)
    dp.include_router(photo.router)
    dp.include_router(document.router)
    dp.include_router(text.router)

    return dp
