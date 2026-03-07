"""Safety net: перехват необработанных исключений."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from claude_bot.errors import get_user_message

log = logging.getLogger("claude-bot.error")


class ErrorMiddleware(BaseMiddleware):
    """Ловит необработанные исключения и отправляет user-friendly ответ."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        try:
            return await handler(event, data)
        except (SystemExit, KeyboardInterrupt):
            raise
        except Exception:
            log.error("Необработанное исключение", exc_info=True)
            try:
                if isinstance(event, Message):
                    await event.answer(get_user_message("unexpected_error"))
                elif isinstance(event, CallbackQuery):
                    await event.answer("Ошибка. Попробуй ещё раз.", show_alert=True)
            except Exception:
                log.error("Не удалось отправить сообщение об ошибке")
            return None
