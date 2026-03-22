"""Модели уведомлений для notify.json."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

WeekDay = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
# category и status — str, чтобы не ломаться на неизвестных значениях из notify.json
# Известные категории: medication, event, todo, reminder
# Известные статусы: active, paused, completed, pending


class RepeatRule(BaseModel):
    """Правило повторения уведомления."""

    type: Literal["daily", "weekly", "monthly"]
    days: list[WeekDay] = Field(default_factory=list)
    time: str = "09:00"
    day: int | None = None  # для monthly (1-31)

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", v):
            raise ValueError(f"Некорректный формат времени: {v!r}, ожидается HH:MM")
        return v


class Notification(BaseModel):
    """Одно уведомление."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    category: str = "reminder"
    datetime: datetime
    remind_before: list[int] = Field(default_factory=lambda: [0])
    repeat: RepeatRule | None = None
    recipients: list[int]
    status: str = "active"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    created_by: int
    sent_reminders: list[int] = Field(default_factory=list)


class NotifyFile(BaseModel):
    """Корневая структура notify.json."""

    notifications: list[Notification] = []
