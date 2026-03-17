"""Форматирование элементов плана в HTML для Telegram (SRP-модуль)."""

from __future__ import annotations

import html as html_lib
from datetime import date, datetime, time

from claude_bot.constants import (
    CATEGORY_EMOJI,
    EMOJI_PLAN_CARRIED,
    EMOJI_REMINDER,
    PLAN_DESC_PREVIEW_LEN,
    PLAN_STATUS_EMOJI,
    PRIORITY_EMOJI,
    PRIORITY_ORDER,
)
from claude_bot.models.planner import PlanItem


def format_day_plan(d: date, items: list[PlanItem], now: datetime) -> str:
    """Форматирует план дня в HTML.

    Сортировка: сначала с time_start (хронологически),
    затем без времени (по приоритету).
    """
    if not items:
        return f"📅 <b>{_format_date_header(d, now)}</b>\n\nПлан пуст."

    sorted_items = sorted(
        items,
        key=lambda x: (
            x.time_start is None,
            x.time_start or time.min,
            PRIORITY_ORDER.get(x.priority, 3),
        ),
    )

    lines = [f"📅 <b>{_format_date_header(d, now)}</b>\n"]

    is_past = d < now.date()
    for item in sorted_items:
        if is_past:
            lines.append(format_item_past(item))
        else:
            lines.append(format_item_current(item, now))

    # Статистика
    total = len(items)
    done_count = sum(1 for i in items if i.status == "done")
    if total > 0:
        pct = done_count * 100 // total
        lines.append(f"\n📊 {done_count}/{total} ({pct}%)")

    return "\n".join(lines)


def format_item_past(item: PlanItem) -> str:
    """Элемент прошлого дня с финальным статусом."""
    title = html_lib.escape(item.title)
    cat_emoji = CATEGORY_EMOJI.get(item.category, EMOJI_REMINDER)

    if item.status == "done":
        line = f"✅ <s>{title}</s>"
    elif item.carried_over and item.carried_from:
        line = f"{EMOJI_PLAN_CARRIED} {title} → перенесено"
    elif item.status == "cancelled":
        line = f"❌ <s>{title}</s>"
    elif item.status == "skipped":
        line = f"⏭ <s>{title}</s>"
    else:
        line = f"⬜ {title}"

    # Время если есть
    if item.time_start:
        time_str = item.time_start.strftime("%H:%M")
        line = f"{cat_emoji} {time_str} {line}"
    else:
        line = f"{cat_emoji} {line}"

    return line


def format_item_future(item: PlanItem) -> str:
    """Элемент будущего дня: время начала + длительность."""
    title = html_lib.escape(item.title)
    cat_emoji = CATEGORY_EMOJI.get(item.category, EMOJI_REMINDER)
    priority_emoji = PRIORITY_EMOJI.get(item.priority, "")

    parts = []
    if item.time_start:
        time_str = item.time_start.strftime("%H:%M")
        if item.time_end and item.time_end > item.time_start:
            duration = _format_duration(item.time_start, item.time_end)
            parts.append(f"{time_str} ({duration})")
        else:
            parts.append(time_str)

    prefix = f"{cat_emoji} "
    if priority_emoji:
        prefix += f"{priority_emoji} "
    if parts:
        prefix += f"{parts[0]} "

    status_emoji = PLAN_STATUS_EMOJI.get(item.status, "⬜")
    return f"{prefix}{status_emoji} {title}"


def format_item_current(item: PlanItem, now: datetime) -> str:
    """Элемент текущего/будущего дня: статус + время + название."""
    title = html_lib.escape(item.title)
    cat_emoji = CATEGORY_EMOJI.get(item.category, EMOJI_REMINDER)
    status_emoji = PLAN_STATUS_EMOJI.get(item.status, "⬜")
    priority_emoji = PRIORITY_EMOJI.get(item.priority, "")

    parts = []

    # Время
    if item.time_start:
        time_str = item.time_start.strftime("%H:%M")
        if item.time_end and item.time_end > item.time_start:
            duration = _format_duration(item.time_start, item.time_end)
            parts.append(f"{time_str} ({duration})")
        else:
            parts.append(time_str)

    prefix = f"{cat_emoji} "
    if parts:
        prefix += f"{parts[0]} "
    if priority_emoji:
        prefix += f"{priority_emoji} "

    line = f"{prefix}{status_emoji} {title}"

    # Пометка «перенесено»
    if item.carried_over:
        line += " <i>(перенесено)</i>"

    # Описание (превью)
    if item.description:
        desc = html_lib.escape(item.description[:PLAN_DESC_PREVIEW_LEN])
        if len(item.description) > PLAN_DESC_PREVIEW_LEN:
            desc += "..."
        line += f"\n    <i>{desc}</i>"

    return line


def format_morning_digest(
    items: list[PlanItem],
    carried: list[PlanItem],
) -> str:
    """Утренний дайджест: план на сегодня."""
    lines = ["☀️ <b>Доброе утро! План на сегодня:</b>\n"]

    if carried:
        lines.append(f"📦 <i>Перенесено из вчера: {len(carried)}</i>\n")

    if not items:
        lines.append("План пуст. Добавь задачи через чат!")
        return "\n".join(lines)

    sorted_items = sorted(
        items,
        key=lambda x: (
            x.time_start is None,
            x.time_start or time.min,
            PRIORITY_ORDER.get(x.priority, 3),
        ),
    )

    for item in sorted_items:
        cat_emoji = CATEGORY_EMOJI.get(item.category, EMOJI_REMINDER)
        title = html_lib.escape(item.title)
        priority_emoji = PRIORITY_EMOJI.get(item.priority, "")

        parts = [cat_emoji]
        if item.time_start:
            time_str = item.time_start.strftime("%H:%M")
            if item.time_end:
                duration = _format_duration(item.time_start, item.time_end)
                parts.append(f"{time_str} ({duration})")
            else:
                parts.append(time_str)
        if priority_emoji:
            parts.append(priority_emoji)
        parts.append(title)
        if item.carried_over:
            parts.append("<i>(перенесено)</i>")

        lines.append(" ".join(parts))

    return "\n".join(lines)


def format_evening_summary(items: list[PlanItem]) -> str:
    """Вечерний итог: выполнено / пропущено / не выполнено + %."""
    lines = ["🌙 <b>Итоги дня:</b>\n"]

    if not items:
        lines.append("На сегодня задач не было.")
        return "\n".join(lines)

    done = [i for i in items if i.status == "done"]
    skipped = [i for i in items if i.status == "skipped"]
    cancelled = [i for i in items if i.status == "cancelled"]
    pending = [i for i in items if i.status in ("pending", "in_progress")]

    total = len(items)
    pct = len(done) * 100 // total if total > 0 else 0

    lines.append(f"✅ Выполнено: {len(done)}")
    if skipped:
        lines.append(f"⏭ Пропущено: {len(skipped)}")
    if cancelled:
        lines.append(f"❌ Отменено: {len(cancelled)}")
    if pending:
        lines.append(f"⬜ Не выполнено: {len(pending)}")

    lines.append(f"\n📊 Completion rate: <b>{pct}%</b>")

    # Список невыполненных
    if pending:
        lines.append("\n<i>Не выполнено:</i>")
        for item in pending:
            title = html_lib.escape(item.title)
            lines.append(f"  • {title}")

    return "\n".join(lines)


def format_week_overview(days: dict[date, list[PlanItem]], now: datetime) -> str:
    """Обзор недели: краткий список по дням."""
    lines = ["📅 <b>Неделя:</b>\n"]

    for d in sorted(days.keys()):
        items = days[d]
        day_name = _day_name_ru(d)
        total = len(items)
        done = sum(1 for i in items if i.status == "done")
        is_today = d == now.date()

        marker = " ← сегодня" if is_today else ""
        if total == 0:
            lines.append(f"  {day_name}{marker} — пусто")
        else:
            pct = done * 100 // total
            lines.append(f"  {day_name}{marker} — {done}/{total} ({pct}%)")

    return "\n".join(lines)


# ── Хелперы ──


def _format_date_header(d: date, now: datetime) -> str:
    """Заголовок даты: 'Сегодня, 17 мар' / 'Завтра, 18 мар' / 'пн, 20 мар'."""
    from datetime import timedelta
    today = now.date()

    if d == today:
        label = "Сегодня"
    elif d == today - timedelta(days=1):
        label = "Вчера"
    elif d == today + timedelta(days=1):
        label = "Завтра"
    elif d == today + timedelta(days=2):
        label = "Послезавтра"
    else:
        label = _day_name_ru(d)

    months = [
        "", "янв", "фев", "мар", "апр", "май", "июн",
        "июл", "авг", "сен", "окт", "ноя", "дек",
    ]
    return f"{label}, {d.day} {months[d.month]}"


def _day_name_ru(d: date) -> str:
    """Название дня недели по-русски."""
    names = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]
    return names[d.weekday()]


def _format_duration(start: time, end: time) -> str:
    """Длительность между time_start и time_end: '1ч 30мин'."""
    start_min = start.hour * 60 + start.minute
    end_min = end.hour * 60 + end.minute
    diff = end_min - start_min
    if diff <= 0:
        return ""
    hours = diff // 60
    minutes = diff % 60
    if hours and minutes:
        return f"{hours}ч {minutes}мин"
    elif hours:
        return f"{hours}ч"
    else:
        return f"{minutes}мин"
