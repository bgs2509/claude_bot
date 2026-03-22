"""Сервис операций с planner.json (чтение, запись, CRUD, миграция)."""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path

from ai_steward.errors import InfrastructureError
from ai_steward.models.planner import (
    PlanItem,
    PlanItemPatch,
    PlanItemStatus,
    PlannerFile,
    RepeatRule,
)

log = logging.getLogger("ai-steward.planner-service")

FILENAME = "planner.json"
OLD_FILENAME = "notify.json"

# Допуск при проверке времени (секунды)
_TIME_TOLERANCE = 90

# Маппинг дней недели → номер isoweekday (пн=1 .. вс=7)
_WEEKDAY_MAP: dict[str, int] = {
    "mon": 1, "tue": 2, "wed": 3, "thu": 4,
    "fri": 5, "sat": 6, "sun": 7,
}

# Статусы, при которых элемент НЕ активен
_INACTIVE_STATUSES = {"done", "cancelled", "skipped"}


def _planner_path(project_path: Path) -> Path:
    return project_path / FILENAME


def _old_notify_path(project_path: Path) -> Path:
    return project_path / OLD_FILENAME


# ── Загрузка / сохранение ──


def load(project_path: Path) -> PlannerFile:
    """Загрузить planner.json. Автомиграция из notify.json если нужно."""
    path = _planner_path(project_path)
    if not path.exists():
        # Попробовать мигрировать из notify.json
        migrated = migrate_from_notify(project_path)
        if migrated >= 0:
            # Миграция прошла (или нечего мигрировать)
            if path.exists():
                return _load_file(path)
        return PlannerFile()
    return _load_file(path)


def _load_file(path: Path) -> PlannerFile:
    """Прочитать и распарсить planner.json."""
    try:
        raw = path.read_text(encoding="utf-8")
        return PlannerFile.model_validate_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        raise InfrastructureError(
            f"Повреждён planner.json: {path}: {e}",
            "planner_parse_error",
        ) from e
    except OSError as e:
        raise InfrastructureError(
            f"Не удалось прочитать {path}: {e}",
            "planner_read_error",
        ) from e


def save(project_path: Path, data: PlannerFile) -> None:
    """Сохранить planner.json."""
    path = _planner_path(project_path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            data.model_dump_json(indent=2),
            encoding="utf-8",
        )
    except OSError as e:
        raise InfrastructureError(
            f"Не удалось записать {path}: {e}",
            "planner_write_error",
        ) from e


# ── CRUD ──


def add(project_path: Path, item: PlanItem) -> list[PlanItem]:
    """Добавить элемент в planner.json.

    Returns:
        Список конфликтующих элементов (пустой если конфликтов нет).
    """
    data = load(project_path)
    # Найти конфликты среди элементов того же дня
    same_day = [i for i in data.items if i.date == item.date and i.status not in _INACTIVE_STATUSES]
    conflicts = find_conflicts(item, same_day)
    data.items.append(item)
    save(project_path, data)
    return conflicts


def remove(project_path: Path, item_id: str) -> bool:
    """Удалить элемент по ID. Возвращает True если найден."""
    data = load(project_path)
    before = len(data.items)
    data.items = [i for i in data.items if i.id != item_id]
    if len(data.items) == before:
        return False
    save(project_path, data)
    return True


def update(project_path: Path, item_id: str, patch: PlanItemPatch) -> PlanItem | None:
    """Обновить элемент. Возвращает обновлённый элемент или None."""
    data = load(project_path)
    for i, item in enumerate(data.items):
        if item.id != item_id:
            continue
        # Применить только заданные поля
        updates = patch.model_dump(exclude_none=True)
        updated = item.model_copy(update=updates)
        data.items[i] = updated
        save(project_path, data)
        return updated
    return None


def get_by_date(project_path: Path, d: date) -> list[PlanItem]:
    """Все элементы плана на указанную дату."""
    data = load(project_path)
    return [i for i in data.items if i.date == d]


def get_active(project_path: Path) -> list[PlanItem]:
    """Все активные элементы (status не в done/cancelled/skipped)."""
    data = load(project_path)
    return [i for i in data.items if i.status not in _INACTIVE_STATUSES]


# ── Статусы ──


def mark_done(project_path: Path, item_id: str) -> bool:
    """Отметить как выполненный."""
    return set_status(project_path, item_id, "done")


def mark_skipped(project_path: Path, item_id: str) -> bool:
    """Отметить как пропущенный."""
    return set_status(project_path, item_id, "skipped")


def set_status(project_path: Path, item_id: str, status: PlanItemStatus) -> bool:
    """Установить статус элемента. Возвращает True если найден."""
    data = load(project_path)
    for item in data.items:
        if item.id == item_id:
            item.status = status
            save(project_path, data)
            return True
    return False


# ── Конфликты ──


def find_conflicts(new_item: PlanItem, existing: list[PlanItem]) -> list[PlanItem]:
    """Найти элементы с пересекающимися временными интервалами.

    Конфликт: оба имеют time_start и интервалы пересекаются.
    """
    if not new_item.time_start:
        return []

    new_start = new_item.time_start
    new_end = new_item.time_end or new_start

    conflicts = []
    for item in existing:
        if item.id == new_item.id:
            continue
        if not item.time_start:
            continue
        ex_start = item.time_start
        ex_end = item.time_end or ex_start
        # Пересечение: start1 < end2 AND start2 < end1
        if new_start < ex_end and ex_start < new_end:
            conflicts.append(item)
    return conflicts


# ── Напоминания (is_due / mark_sent) ──


def _parse_time(time_str: str) -> tuple[int, int]:
    """Парсить 'HH:MM' в (hour, minute)."""
    parts = time_str.split(":")
    return int(parts[0]), int(parts[1])


def _matches_repeat_schedule(repeat: RepeatRule, now: datetime) -> bool:
    """Проверить совпадение текущего момента с расписанием повтора."""
    hour, minute = _parse_time(repeat.time)

    if repeat.type == "daily":
        pass
    elif repeat.type == "weekly":
        if now.isoweekday() not in [_WEEKDAY_MAP[d] for d in repeat.days]:
            return False
    elif repeat.type == "monthly":
        if repeat.day is not None and now.day != repeat.day:
            return False

    scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    diff = abs((now - scheduled).total_seconds())
    return diff <= _TIME_TOLERANCE


def is_due(item: PlanItem, now: datetime) -> list[int]:
    """Проверить, какие напоминания нужно отправить.

    Args:
        item: Элемент плана для проверки.
        now: Текущее время (aware, в часовом поясе планировщика).

    Returns:
        Список значений remind_before (минут), которые сейчас нужно отправить.
    """
    if item.status in _INACTIVE_STATUSES:
        return []

    due_reminders: list[int] = []

    if item.repeat:
        # Повторяющееся: проверяем расписание
        if not _matches_repeat_schedule(item.repeat, now):
            return []
        for minutes in item.remind_before:
            if minutes in item.sent_reminders:
                continue
            if minutes == 0:
                due_reminders.append(0)
            else:
                hour, minute = _parse_time(item.repeat.time)
                scheduled = now.replace(
                    hour=hour, minute=minute, second=0, microsecond=0,
                )
                trigger_time = scheduled - timedelta(minutes=minutes)
                diff = abs((now - trigger_time).total_seconds())
                if diff <= _TIME_TOLERANCE:
                    due_reminders.append(minutes)
    elif item.time_start:
        # Одноразовое с временем: проверяем date + time_start
        today = now.date()
        if item.date != today:
            return []
        for minutes in item.remind_before:
            if minutes in item.sent_reminders:
                continue
            event_dt = now.replace(
                hour=item.time_start.hour,
                minute=item.time_start.minute,
                second=0, microsecond=0,
            )
            trigger_time = event_dt - timedelta(minutes=minutes)
            diff = (now - trigger_time).total_seconds()
            if -_TIME_TOLERANCE <= diff <= _TIME_TOLERANCE:
                due_reminders.append(minutes)

    return due_reminders


def mark_sent(
    project_path: Path,
    item: PlanItem,
    sent_minutes: list[int],
) -> None:
    """Пометить напоминания как отправленные.

    Для повторяющихся — сбрасывает sent_reminders после полного цикла.
    """
    data = load(project_path)
    for i in data.items:
        if i.id != item.id:
            continue

        i.sent_reminders.extend(sent_minutes)

        # Все напоминания отправлены?
        all_sent = set(i.remind_before).issubset(set(i.sent_reminders))
        if all_sent and i.repeat:
            # Повторяющееся — сбросить для следующего срабатывания
            i.sent_reminders = []
        break

    save(project_path, data)


def get_missed(
    project_path: Path,
    now: datetime,
    grace_minutes: int = 30,
) -> list[PlanItem]:
    """Найти пропущенные одноразовые элементы (время прошло давно)."""
    data = load(project_path)
    missed = []
    grace = timedelta(minutes=grace_minutes)
    today = now.date()
    for item in data.items:
        if item.status != "pending":
            continue
        if item.repeat:
            continue
        if not item.time_start:
            continue
        if item.date > today:
            continue
        event_dt = now.replace(
            year=item.date.year, month=item.date.month, day=item.date.day,
            hour=item.time_start.hour, minute=item.time_start.minute,
            second=0, microsecond=0,
        )
        if event_dt < now - grace:
            missed.append(item)
    return missed


# ── Миграция notify.json → planner.json ──


def migrate_from_notify(project_path: Path) -> int:
    """Мигрировать notify.json → planner.json.

    Returns:
        Количество мигрированных записей. -1 если нечего мигрировать.
    """
    old_path = _old_notify_path(project_path)
    new_path = _planner_path(project_path)

    if new_path.exists():
        return -1  # planner.json уже есть
    if not old_path.exists():
        return -1  # notify.json нет

    try:
        raw = old_path.read_text(encoding="utf-8")
        old_data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as e:
        log.warning("Миграция: ошибка чтения %s: %s", old_path, e)
        return -1

    notifications = old_data.get("notifications", [])
    items: list[PlanItem] = []

    for n in notifications:
        try:
            item = _convert_notification(n)
            items.append(item)
        except Exception as e:
            log.warning("Миграция: пропуск записи %s: %s", n.get("id", "?"), e)

    if items:
        pf = PlannerFile(items=items)
        save(project_path, pf)

    # Переименовать старый файл
    backup_path = old_path.with_suffix(".json.bak")
    try:
        old_path.rename(backup_path)
        log.info("Миграция: %s → %s (%d записей)", old_path.name, FILENAME, len(items))
    except OSError as e:
        log.warning("Миграция: не удалось переименовать %s: %s", old_path, e)

    return len(items)


def _convert_notification(n: dict) -> PlanItem:
    """Конвертировать одну запись Notification → PlanItem."""
    # Парсить datetime
    dt_raw = n.get("datetime", "")
    if isinstance(dt_raw, str):
        dt = datetime.fromisoformat(dt_raw)
    else:
        dt = dt_raw

    # Маппинг статуса
    old_status = n.get("status", "active")
    status_map = {
        "active": "pending",
        "paused": "pending",
        "completed": "done",
    }
    status = status_map.get(old_status, "pending")

    # remind_before: гарантировать что 0 всегда есть
    remind_before = n.get("remind_before", [0])
    if 0 not in remind_before:
        remind_before.append(0)

    # RepeatRule
    repeat_data = n.get("repeat")
    repeat = RepeatRule(**repeat_data) if repeat_data else None

    return PlanItem(
        id=n.get("id", ""),
        title=n.get("title", ""),
        description=n.get("description", ""),
        category=n.get("category", "reminder"),
        priority="none",
        date=dt.date() if hasattr(dt, "date") else date.today(),
        time_start=dt.time() if hasattr(dt, "time") else None,
        time_end=None,
        deadline=None,
        remind_before=remind_before,
        repeat=repeat,
        recipients=n.get("recipients", []),
        status=status,
        carried_over=False,
        carried_from=None,
        created_at=datetime.fromisoformat(n["created_at"]) if n.get("created_at") else datetime.now(timezone.utc),
        created_by=n.get("created_by"),
        sent_reminders=n.get("sent_reminders", []),
    )
