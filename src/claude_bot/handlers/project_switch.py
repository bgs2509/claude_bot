"""Перехват reply-кнопок быстрого переключения проекта."""

import logging
import os
from pathlib import Path

from aiogram import Router
from aiogram.filters import BaseFilter
from aiogram.types import Message, ReactionTypeEmoji

from claude_bot.config import Settings, get_user_projects_dir
from claude_bot.keyboards import build_paginated_keyboard, build_project_reply_keyboard
from claude_bot.services.storage import SessionStorage

router = Router(name="project_switch")
log = logging.getLogger("claude-bot.project_switch")

# Служебные кнопки
_BUTTON_MORE = "📋 Ещё"
_BUTTON_HOME = "🏠 Общий"
_PREFIX_ACTIVE = "▶️ "
_PREFIX_INACTIVE = "📁 "


def _parse_project_button(text: str) -> tuple[str | None, str | None]:
    """Извлечь тип и имя проекта из текста кнопки.

    Returns:
        (button_type, project_name): тип кнопки и имя проекта.
        button_type: "active", "inactive", "more", "home" или None.
    """
    if text == _BUTTON_MORE:
        return "more", None
    if text == _BUTTON_HOME:
        return "home", None
    if text.startswith(_PREFIX_ACTIVE):
        return "active", text[len(_PREFIX_ACTIVE):]
    if text.startswith(_PREFIX_INACTIVE):
        return "inactive", text[len(_PREFIX_INACTIVE):]
    return None, None


class ProjectButtonFilter(BaseFilter):
    """Фильтр: сообщение — нажатие reply-кнопки проекта."""

    async def __call__(
        self,
        message: Message,
        settings: Settings,
        storage: SessionStorage | None = None,
    ) -> bool | dict:
        if not message.text or not storage or not message.from_user:
            return False

        button_type, name = _parse_project_button(message.text)
        if button_type is None:
            return False

        # Для кнопок проектов — проверить что проект существует
        if button_type in ("active", "inactive"):
            uid = message.from_user.id
            projects_dir = get_user_projects_dir(settings, uid)
            projects = storage.list_projects(projects_dir)
            if name not in projects:
                return False

        return {"button_type": button_type, "project_name": name}


@router.message(ProjectButtonFilter())
async def handle_project_button(
    message: Message,
    settings: Settings,
    storage: SessionStorage,
    button_type: str,
    project_name: str | None,
) -> None:
    """Обработать нажатие reply-кнопки проекта."""
    uid = message.from_user.id
    projects_dir = get_user_projects_dir(settings, uid)

    if button_type == "more":
        await _handle_more(message, storage, projects_dir)
        return

    if button_type == "home":
        await _handle_home(message, storage, settings, uid, projects_dir)
        return

    # active или inactive — переключить проект
    await _handle_switch(message, storage, settings, uid, projects_dir, project_name)


async def _handle_more(
    message: Message,
    storage: SessionStorage,
    projects_dir: Path,
) -> None:
    """Показать полный список проектов инлайн-клавиатурой."""
    projects = storage.list_projects(projects_dir)
    items = [(p, f"p:sel:{p[:50]}") for p in projects]
    markup = build_paginated_keyboard(
        items=items, page=0,
        new_callback="p:new", back_callback="m:main",
        more_prefix="p:list:",
    )
    await message.answer("Все проекты:", reply_markup=markup)


async def _handle_home(
    message: Message,
    storage: SessionStorage,
    settings: Settings,
    uid: int,
    projects_dir: Path,
) -> None:
    """Сбросить активный проект."""
    user = storage.get_user(uid)
    if user.active_project is None:
        await message.react([ReactionTypeEmoji(emoji="👌")])
        return

    old_project = user.active_project
    await storage.clear_active_project(uid)
    log.info(
        "project_switch: %s → (общий), uid=%d",
        old_project, uid,
    )

    keyboard = build_project_reply_keyboard(
        storage.list_projects(projects_dir), None,
    )
    await message.react([ReactionTypeEmoji(emoji="👌")])
    await message.answer("🏠 Общий", reply_markup=keyboard)


async def _handle_switch(
    message: Message,
    storage: SessionStorage,
    settings: Settings,
    uid: int,
    projects_dir: Path,
    project_name: str,
) -> None:
    """Переключить на указанный проект."""
    user = storage.get_user(uid)

    # Нажали текущий проект — реакция «уже активен»
    if user.active_project == project_name:
        await message.react([ReactionTypeEmoji(emoji="👌")])
        return

    old_project = user.active_project
    await storage.set_active_project(uid, project_name, projects_dir)

    # Обновить mtime для сортировки
    project_path = projects_dir / project_name
    os.utime(project_path, None)

    # Восстановить последнюю сессию
    session_name = await storage.restore_last_session(uid)

    log.info(
        "project_switch: %s → %s, session=%s, uid=%d",
        old_project or "(общий)", project_name,
        session_name or "новая", uid,
    )

    keyboard = build_project_reply_keyboard(
        storage.list_projects(projects_dir), project_name,
    )
    label = f"▶️ {project_name}"
    if session_name:
        label += f" · {session_name}"
    await message.react([ReactionTypeEmoji(emoji="👌")])
    await message.answer(label, reply_markup=keyboard)
