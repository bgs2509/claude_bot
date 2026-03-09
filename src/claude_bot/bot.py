"""Фабрики для создания бота и диспетчера."""

from aiogram import Bot, Dispatcher

from claude_bot.config import Settings
from claude_bot.handlers import commands, document, photo, text, voice
from claude_bot.middlewares.auth import AuthMiddleware
from claude_bot.services.ai.manager import AIManager
from claude_bot.state import AppState


def create_bot(settings: Settings) -> Bot:
    """Создать экземпляр бота."""
    return Bot(token=settings.telegram_bot_token)


def create_dispatcher(settings: Settings, state: AppState, ai_manager: AIManager) -> Dispatcher:
    """Создать диспетчер с зарегистрированными роутерами и middleware."""
    dp = Dispatcher()

    # Middleware авторизации (на все Message)
    dp.message.middleware(AuthMiddleware(settings, state, ai_manager))

    # Роутеры (порядок важен: text последним — ловит всё)
    dp.include_router(commands.router)
    dp.include_router(voice.router)
    dp.include_router(photo.router)
    dp.include_router(document.router)
    dp.include_router(text.router)

    return dp
