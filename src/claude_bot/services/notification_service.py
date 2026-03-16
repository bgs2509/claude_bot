"""Сервис операций с notify.json (чтение, запись, CRUD)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from claude_bot.errors import InfrastructureError
from claude_bot.models.notification import (
    Notification,
    NotifyFile,
    RepeatRule,
)

log = logging.getLogger("claude-bot.notification-service")

FILENAME = "notify.json"

# Допуск при проверке времени (секунды)
_TIME_TOLERANCE = 90

# Маппинг дней недели → номер isoweekday (пн=1 .. вс=7)
_WEEKDAY_MAP: dict[str, int] = {
    "mon": 1, "tue": 2, "wed": 3, "thu": 4,
    "fri": 5, "sat": 6, "sun": 7,
}


def _notify_path(project_path: Path) -> Path:
    return project_path / FILENAME


def load(project_path: Path) -> NotifyFile:
    """Загрузить notify.json. Возвращает пустой NotifyFile если файла нет."""
    path = _notify_path(project_path)
    if not path.exists():
        return NotifyFile()
    try:
        raw = path.read_text(encoding="utf-8")
        return NotifyFile.model_validate_json(raw)
    except json.JSONDecodeError as e:
        raise InfrastructureError(
            f"Повреждён notify.json: {path}: {e}",
            "notify_parse_error",
        ) from e
    except OSError as e:
        raise InfrastructureError(
            f"Не удалось прочитать {path}: {e}",
            "notify_read_error",
        ) from e


def save(project_path: Path, data: NotifyFile) -> None:
    """Сохранить notify.json."""
    path = _notify_path(project_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            data.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        raise InfrastructureError(
            f"Не удалось записать {path}: {e}",
            "notify_write_error",
        ) from e


def add(project_path: Path, notification: Notification) -> None:
    """Добавить уведомление в notify.json."""
    data = load(project_path)
    data.notifications.append(notification)
    save(project_path, data)


def remove(project_path: Path, notification_id: str) -> bool:
    """Удалить уведомление по ID. Возвращает True если найдено."""
    data = load(project_path)
    before = len(data.notifications)
    data.notifications = [n for n in data.notifications if n.id != notification_id]
    if len(data.notifications) == before:
        return False
    save(project_path, data)
    return True


def get_active(project_path: Path) -> list[Notification]:
    """Все активные уведомления проекта."""
    data = load(project_path)
    return [n for n in data.notifications if n.status == "active"]


def _parse_time(time_str: str) -> tuple[int, int]:
    """Парсить 'HH:MM' в (hour, minute)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def _matches_repeat_schedule(repeat: RepeatRule, now: datetime) -> bool:
    """Проверить, совпадает ли текущий момент с расписанием повтора."""
    hour, minute = _parse_time(repeat.time)

    if repeat.type == "daily":
        pass  # каждый день
    elif repeat.type == "weekly":
        if now.isoweekday() not in [_WEEKDAY_MAP[d] for d in repeat.days]:
            return False
    elif repeat.type == "monthly":
        if repeat.day is not None and now.day != repeat.day:
            return False

    # Проверяем совпадение времени с допуском
    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    diff = abs((now - scheduled).total_seconds())
    return diff <= _TIME_TOLERANCE


def _ensure_aware(dt: datetime) -> datetime:
    """Привести datetime к UTC-aware если naive."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def is_due(notification: Notification, now: datetime) -> list[int]:
    """Проверить, какие напоминания нужно отправить.

    Returns:
        Список значений remind_before (минут), которые сейчас нужно отправить.
        Пустой список — ничего не отправлять.
    """
    if notification.status != "active":
        return []

    due_reminders: list[int] = []
    now = _ensure_aware(now)

    if notification.repeat:
        # Повторяющееся: проверяем расписание
        if not _matches_repeat_schedule(notification.repeat, now):
            return []
        # remind_before=0 означает "в момент события"
        for minutes in notification.remind_before:
            if minutes in notification.sent_reminders:
                continue
            if minutes == 0:
                due_reminders.append(0)
            else:
                # Для повторяющихся: напомнить за N минут до scheduled time
                hour, minute = _parse_time(notification.repeat.time)
                scheduled = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0,
                )
                trigger_time = scheduled - timedelta(minutes=minutes)
                diff = abs((now - trigger_time).total_seconds())
                if diff <= _TIME_TOLERANCE:
                    due_reminders.append(minutes)
    else:
        # Одноразовое: проверяем datetime
        for minutes in notification.remind_before:
            if minutes in notification.sent_reminders:
                continue
            trigger_time = _ensure_aware(notification.datetime) - timedelta(minutes=minutes)
            diff = (now - trigger_time).total_seconds()
            # Уведомление пора отправить если время наступило (с допуском)
            if -_TIME_TOLERANCE <= diff <= _TIME_TOLERANCE:
                due_reminders.append(minutes)

    return due_reminders


def mark_sent(
    project_path: Path,
    notification: Notification,
    sent_minutes: list[int],
) -> None:
    """Пометить напоминания как отправленные.

    Для одноразовых — ставит status='completed' после всех remind_before.
    Для повторяющихся — сбрасывает sent_reminders после полного цикла.
    """
    data = load(project_path)
    for n in data.notifications:
        if n.id != notification.id:
            continue

        n.sent_reminders.extend(sent_minutes)

        # Все напоминания отправлены?
        all_sent = set(n.remind_before).issubset(set(n.sent_reminders))
        if all_sent:
            if n.repeat:
                # Повторяющееся — сбросить для следующего срабатывания
                n.sent_reminders = []
            else:
                # Одноразовое — завершить
                n.status = "completed"
        break

    save(project_path, data)


def get_missed(
    project_path: Path,
    now: datetime,
    grace_minutes: int = 30,
) -> list[Notification]:
    """Найти пропущенные одноразовые уведомления (datetime прошёл давно).

    Используется при старте бота для оповещения о пропусках.
    """
    data = load(project_path)
    missed = []
    grace = timedelta(minutes=grace_minutes)
    for n in data.notifications:
        if n.status != "active":
            continue
        if n.repeat:
            continue  # повторяющиеся не пропускаются
        if _ensure_aware(n.datetime) < now - grace:
            missed.append(n)
    return missed
