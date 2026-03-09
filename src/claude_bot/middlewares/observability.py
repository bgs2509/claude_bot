"""ObservabilityMiddleware — трейсинг каждого запроса."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from claude_bot.context import (
    obs_output_var,
    obs_status_var,
    request_id_var,
    user_id_var,
)

if TYPE_CHECKING:
    from claude_bot.services.analytics import EventLogger

log = logging.getLogger("claude-bot.observability")


def _detect_event_type(event: TelegramObject) -> str:
    """Определить тип события по объекту aiogram."""
    if isinstance(event, Message):
        if event.text and event.text.startswith("/"):
            return "command"
        if event.text:
            return "text"
        if event.voice:
            return "voice"
        if event.photo:
            return "photo"
        if event.document:
            return "document"
        return "other"
    if isinstance(event, CallbackQuery):
        return "callback"
    return "other"


def _input_summary(event: TelegramObject, max_len: int = 120) -> str:
    """Краткое описание входных данных."""
    if isinstance(event, Message):
        if event.text:
            return event.text[:max_len]
        if event.voice:
            dur = event.voice.duration or 0
            return f"voice:{dur}s"
        if event.photo:
            return f"photo:{event.caption[:max_len] if event.caption else ''}"
        if event.document:
            return f"doc:{event.document.file_name or 'unnamed'}"
    if isinstance(event, CallbackQuery):
        return f"cb:{event.data or ''}"
    return ""


class ObservabilityMiddleware(BaseMiddleware):
    """Измеряет latency, определяет тип события, записывает финальный лог."""

    def __init__(self, event_logger: EventLogger | None = None) -> None:
        self._event_logger = event_logger

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        # Сбросить observability-контекст
        obs_status_var.set("ok")
        obs_output_var.set("")

        event_type = _detect_event_type(event)
        summary = _input_summary(event)

        start = time.monotonic()
        try:
            result = await handler(event, data)
        except Exception:
            obs_status_var.set("exception")
            raise
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            status = obs_status_var.get("ok")
            output = obs_output_var.get("")
            req_id = request_id_var.get("---")
            uid_str = user_id_var.get("---")

            log.info(
                "event=%s duration=%dms status=%s",
                event_type,
                duration_ms,
                status,
                extra={
                    "event_type": event_type,
                    "duration_ms": duration_ms,
                    "status": status,
                    "input_summary": summary[:120],
                    "output_summary": output[:80],
                },
            )

            if self._event_logger:
                uid = int(uid_str) if uid_str != "---" else None
                asyncio.create_task(
                    self._event_logger.log_event(
                        request_id=req_id,
                        user_id=uid,
                        event_type=event_type,
                        input_summary=summary,
                        output_summary=output,
                        duration_ms=duration_ms,
                        status=status,
                    )
                )

        return result
