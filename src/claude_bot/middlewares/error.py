"""Safety net: перехват необработанных исключений."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, Message, TelegramObject

from claude_bot.errors import AppError, DomainError, get_user_message

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
        except DomainError as exc:
            log.warning("Domain error: %s", exc)
            msg = get_user_message(exc.user_message_key)
            try:
                if isinstance(event, Message):
                    await event.answer(msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(msg, show_alert=True)
            except Exception:
                log.error("Не удалось отправить сообщение об ошибке")
            return None
        except AppError as exc:
            log.error("App error: %s", exc, exc_info=True)
            msg = get_user_message(exc.user_message_key)
            try:
                if isinstance(event, Message):
                    await event.answer(msg)
                elif isinstance(event, CallbackQuery):
                    await event.answer(msg, show_alert=True)
            except Exception:
                log.error("Не удалось отправить сообщение об ошибке")
            return None
        except Exception as exc:
            # Безобидный race condition при двойном нажатии кнопки
            if isinstance(exc, TelegramBadRequest) and "is not modified" in str(exc):
                log.debug("edit_text не изменил сообщение: %s", exc)
                return None
            log.error("Необработанное исключение", exc_info=True)
            try:
                import sentry_sdk
                sentry_sdk.capture_exception()
            except Exception:
                pass
            try:
                if isinstance(event, Message):
                    await event.answer(get_user_message("unexpected_error"))
                elif isinstance(event, CallbackQuery):
                    await event.answer("Ошибка. Попробуй ещё раз.", show_alert=True)
            except Exception:
                log.error("Не удалось отправить сообщение об ошибке")
            return None
