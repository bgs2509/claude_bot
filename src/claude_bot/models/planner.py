"""Модели планировщика для planner.json."""

import re
import uuid
from datetime import date, datetime, time, timezone
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

WeekDay = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]

PlanItemStatus = Literal[
    "pending", "in_progress", "done", "skipped", "cancelled",
]

PlanItemPriority = Literal["high", "medium", "low", "none"]


class RepeatRule(BaseModel):
    """Правило повторения элемента плана."""

    type: Literal["daily", "weekly", "monthly"]
    days: list[WeekDay] = Field(default_factory=list)
    time: str = "09:00"
    day: Optional[int] = None  # для monthly (1-31)

    @field_validator("time")
    @classmethod
    def validate_time_format(cls, v: str) -> str:
        if not re.match(r"^(?:[01]\d|2[0-3]):[0-5]\d$", v):
            raise ValueError(f"Некорректный формат времени: {v!r}, ожидается HH:MM")
        return v


class PlanItemPatch(BaseModel):
    """Частичное обновление PlanItem (все поля опциональны)."""

    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[PlanItemPriority] = None
    date: Optional[date] = None
    time_start: Optional[time] = None
    time_end: Optional[time] = None
    deadline: Optional[datetime] = None
    remind_before: Optional[list[int]] = None
    repeat: Optional[RepeatRule] = None
    recipients: Optional[list[int]] = None
    status: Optional[PlanItemStatus] = None


class PlanItem(BaseModel):
    """Элемент плана (задача, событие, блок, напоминание)."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: str = ""
    category: str = "task"  # task, event, block, medication, reminder, ...
    priority: PlanItemPriority = "none"
    date: date  # день привязки
    time_start: Optional[time] = None  # HH:MM начала
    time_end: Optional[time] = None  # HH:MM конца
    deadline: Optional[datetime] = None
    remind_before: list[int] = Field(default_factory=lambda: [0])
    repeat: Optional[RepeatRule] = None
    recipients: list[int] = Field(default_factory=list)
    status: PlanItemStatus = "pending"
    carried_over: bool = False
    carried_from: Optional[date] = None
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    created_by: Optional[int] = None
    sent_reminders: list[int] = Field(default_factory=list)


class PlannerFile(BaseModel):
    """Корневая структура planner.json."""

    items: list[PlanItem] = Field(default_factory=list)
    last_carry_date: Optional[date] = None
