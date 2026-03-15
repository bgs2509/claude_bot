"""Билдер inline- и reply-клавиатур для меню проектов и сессий."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)


def build_main_menu(
    recent_projects: list[str],
    recent_sessions: list[tuple[str, str]],  # [(name, session_id)]
    active_project: str | None,
    active_session_id: str | None,
) -> InlineKeyboardMarkup:
    """Компактное главное меню: заголовки, New, последние элементы."""
    rows: list[list[InlineKeyboardButton]] = []

    # Заголовки — ведут на полные списки
    rows.append([
        InlineKeyboardButton(text="Projects", callback_data="p:list:0"),
        InlineKeyboardButton(text="Sessions", callback_data="s:list:0"),
    ])

    # Кнопки создания
    rows.append([
        InlineKeyboardButton(text="+ New proj", callback_data="p:new"),
        InlineKeyboardButton(text="+ New sess", callback_data="s:new"),
    ])

    # Последние проекты и сессии (до 3)
    max_items = max(len(recent_projects), len(recent_sessions))
    for i in range(min(max_items, 3)):
        row: list[InlineKeyboardButton] = []

        if i < len(recent_projects):
            pname = recent_projects[i]
            label = f">> {pname}" if pname == active_project else pname
            # Ограничиваем callback_data 64 байтами
            cb = f"p:sel:{pname[:50]}"
            row.append(InlineKeyboardButton(text=label, callback_data=cb))
        else:
            row.append(InlineKeyboardButton(text=" ", callback_data="noop"))

        if i < len(recent_sessions):
            sname, sid = recent_sessions[i]
            label = f">> {sname}" if sid == active_session_id else sname
            # Используем короткий id (первые 20 символов)
            cb = f"s:sel:{sid[:50]}"
            row.append(InlineKeyboardButton(text=label, callback_data=cb))
        else:
            row.append(InlineKeyboardButton(text=" ", callback_data="noop"))

        rows.append(row)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_paginated_keyboard(
    items: list[tuple[str, str]],  # [(label, callback_data)]
    page: int,
    new_callback: str,
    back_callback: str,
    more_prefix: str,
    per_page: int = 5,
) -> InlineKeyboardMarkup:
    """Список с пагинацией. Универсален для Projects и Sessions."""
    rows: list[list[InlineKeyboardButton]] = []

    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    for label, cb_data in page_items:
        rows.append([InlineKeyboardButton(text=label, callback_data=cb_data)])

    # Навигация по страницам
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="<< Назад", callback_data=f"{more_prefix}{page - 1}",
        ))
    if end < len(items):
        nav_row.append(InlineKeyboardButton(
            text="Ещё >>", callback_data=f"{more_prefix}{page + 1}",
        ))
    if nav_row:
        rows.append(nav_row)

    # Кнопка создания + возврат
    rows.append([
        InlineKeyboardButton(text="+ New", callback_data=new_callback),
        InlineKeyboardButton(text="<< Menu", callback_data=back_callback),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_project_reply_keyboard(
    projects: list[str],
    active_project: str | None,
    max_buttons: int = 6,
) -> ReplyKeyboardMarkup:
    """Reply-клавиатура с проектами для быстрого переключения.

    Args:
        projects: Список имён проектов (отсортирован по mtime).
        active_project: Имя текущего активного проекта.
        max_buttons: Максимум кнопок проектов (без служебных).
    """
    buttons: list[str] = []

    # Текущий проект первым с маркером
    if active_project and active_project in projects:
        buttons.append(f"📂 {active_project}")
        remaining = [p for p in projects if p != active_project]
    else:
        remaining = list(projects)

    # Остальные с префиксом 📁
    for p in remaining[: max_buttons - len(buttons)]:
        buttons.append(f"📁 {p}")

    # "Ещё" если есть скрытые проекты
    if len(projects) > len(buttons):
        buttons.append("📋 Ещё")

    # Всегда "Общий"
    buttons.append("🏠 Общий")

    # Раскладка по 2 в ряд
    rows: list[list[KeyboardButton]] = []
    for i in range(0, len(buttons), 2):
        row = [KeyboardButton(text=buttons[i])]
        if i + 1 < len(buttons):
            row.append(KeyboardButton(text=buttons[i + 1]))
        rows.append(row)

    return ReplyKeyboardMarkup(
        keyboard=rows,
        resize_keyboard=True,
        is_persistent=True,
    )
