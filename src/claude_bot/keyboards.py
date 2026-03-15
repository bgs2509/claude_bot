"""Билдер inline- и reply-клавиатур."""

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from claude_bot.constants import (
    BUTTON_CREATE_PROJECT,
    BUTTON_HOME,
    BUTTON_MORE,
    EMOJI_ACTIVE,
    EMOJI_CREATE,
    EMOJI_HOME,
    EMOJI_INACTIVE,
    EMOJI_MORE,
    EMOJI_SESSION,
)


def build_status_keyboard(
    projects: list[str],
    active_project: str | None,
) -> InlineKeyboardMarkup:
    """Inline-клавиатура для /status: проекты + служебные кнопки."""
    rows: list[list[InlineKeyboardButton]] = []

    for name in projects[:5]:
        emoji = EMOJI_ACTIVE if name == active_project else EMOJI_INACTIVE
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=f"st:proj:{name[:50]}",
        )])

    if len(projects) > 5:
        rows.append([InlineKeyboardButton(
            text=f"{EMOJI_MORE} Ещё", callback_data="p:list:1",
        )])

    # Служебные кнопки
    rows.append([
        InlineKeyboardButton(
            text=f"{EMOJI_HOME} Общий", callback_data="st:home",
        ),
        InlineKeyboardButton(
            text=f"{EMOJI_CREATE} Проект", callback_data="st:newproj",
        ),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_sessions_keyboard(
    sessions: list[tuple[str, str]],
    active_session_id: str | None,
    page: int = 0,
    per_page: int = 5,
) -> InlineKeyboardMarkup:
    """Inline-клавиатура со списком сессий проекта."""
    rows: list[list[InlineKeyboardButton]] = []

    start = page * per_page
    page_sessions = sessions[start:start + per_page]

    for name, sid in page_sessions:
        emoji = EMOJI_ACTIVE if sid == active_session_id else EMOJI_SESSION
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {name}",
            callback_data=f"st:ssel:{sid[:50]}",
        )])

    # Пагинация
    nav_row: list[InlineKeyboardButton] = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(
            text="<< Назад", callback_data=f"st:sess:{page - 1}",
        ))
    if start + per_page < len(sessions):
        nav_row.append(InlineKeyboardButton(
            text="Ещё >>", callback_data=f"st:sess:{page + 1}",
        ))
    if nav_row:
        rows.append(nav_row)

    # Служебные кнопки
    rows.append([
        InlineKeyboardButton(
            text=f"{EMOJI_CREATE} Сессия", callback_data="st:newsess",
        ),
        InlineKeyboardButton(text="← Назад", callback_data="st:main"),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_paginated_keyboard(
    items: list[tuple[str, str]],
    page: int,
    new_callback: str,
    back_callback: str,
    more_prefix: str,
    per_page: int = 5,
) -> InlineKeyboardMarkup:
    """Список с пагинацией (для reply KB «Ещё»)."""
    rows: list[list[InlineKeyboardButton]] = []

    start = page * per_page
    end = start + per_page
    page_items = items[start:end]

    for label, cb_data in page_items:
        rows.append([InlineKeyboardButton(text=label, callback_data=cb_data)])

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

    rows.append([
        InlineKeyboardButton(text=f"{EMOJI_CREATE} Проект", callback_data=new_callback),
        InlineKeyboardButton(text="← Меню", callback_data=back_callback),
    ])

    return InlineKeyboardMarkup(inline_keyboard=rows)


def build_project_reply_keyboard(
    projects: list[str],
    active_project: str | None,
    max_buttons: int = 6,
) -> ReplyKeyboardMarkup:
    """Reply-клавиатура с проектами для быстрого переключения."""
    buttons: list[str] = []

    # Текущий проект первым
    if active_project and active_project in projects:
        buttons.append(f"{EMOJI_ACTIVE} {active_project}")
        remaining = [p for p in projects if p != active_project]
    else:
        remaining = list(projects)

    for p in remaining[: max_buttons - len(buttons)]:
        buttons.append(f"{EMOJI_INACTIVE} {p}")

    if len(projects) > len(buttons):
        buttons.append(BUTTON_MORE)

    # Служебные кнопки в последнем ряду
    buttons.append(BUTTON_CREATE_PROJECT)
    buttons.append(BUTTON_HOME)

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
