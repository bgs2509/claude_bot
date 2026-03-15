"""Обработчики главного меню: навигация по проектам и сессиям."""

import logging
import re

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from claude_bot.config import Settings, get_user_projects_dir
from claude_bot.keyboards import build_main_menu, build_paginated_keyboard
from claude_bot.services.storage import SessionStorage

router = Router(name="menu")
log = logging.getLogger("claude-bot.menu")


# ── FSM для создания проекта ──

class CreateProject(StatesGroup):
    waiting_name = State()


# ── Хелперы ──

def _menu_text(storage: SessionStorage, uid: int) -> str:
    """Текст для главного меню с контекстом."""
    user = storage.get_user(uid)
    proj = user.active_project or "—"
    sess = storage.get_active_session_name(uid) or "—"
    return f"Project: {proj}\nSession: {sess}"


def _main_menu_markup(storage: SessionStorage, uid: int, settings: Settings):
    """Собрать InlineKeyboardMarkup для главного меню."""
    user = storage.get_user(uid)
    projects_dir = get_user_projects_dir(settings, uid)
    recent_projects = storage.list_projects(projects_dir, limit=3)
    recent_sessions = [
        (s.name, s.id) for s in storage.get_recent_sessions(uid, limit=3)
    ]
    return build_main_menu(
        recent_projects=recent_projects,
        recent_sessions=recent_sessions,
        active_project=user.active_project,
        active_session_id=storage.get_active_session_id(uid),
    )


# ── /menu ──

@router.message(Command("menu"))
async def cmd_menu(message: Message, storage: SessionStorage, settings: Settings) -> None:
    uid = message.from_user.id
    text = _menu_text(storage, uid)
    markup = _main_menu_markup(storage, uid, settings)
    await message.answer(text, reply_markup=markup)


# ── Главное меню (callback) ──

@router.callback_query(F.data == "m:main")
async def cb_main_menu(callback: CallbackQuery, storage: SessionStorage, settings: Settings) -> None:
    uid = callback.from_user.id
    text = _menu_text(storage, uid)
    markup = _main_menu_markup(storage, uid, settings)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


# ── Проекты: полный список ──

@router.callback_query(F.data.startswith("p:list:"))
async def cb_project_list(callback: CallbackQuery, storage: SessionStorage, settings: Settings) -> None:
    uid = callback.from_user.id
    page = int(callback.data.split(":")[2])
    projects_dir = get_user_projects_dir(settings, uid)
    projects = storage.list_projects(projects_dir)
    active = storage.get_user(uid).active_project

    items = []
    for name in projects:
        label = f">> {name}" if name == active else name
        items.append((label, f"p:sel:{name[:50]}"))

    markup = build_paginated_keyboard(
        items=items,
        page=page,
        new_callback="p:new",
        back_callback="m:main",
        more_prefix="p:list:",
    )
    await callback.message.edit_text("Projects:", reply_markup=markup)
    await callback.answer()


# ── Проекты: выбор ──

@router.callback_query(F.data.startswith("p:sel:"))
async def cb_select_project(callback: CallbackQuery, storage: SessionStorage, settings: Settings) -> None:
    uid = callback.from_user.id
    name = callback.data[6:]  # после "p:sel:"
    projects_dir = get_user_projects_dir(settings, uid)
    ok = await storage.set_active_project(uid, name, projects_dir)
    if not ok:
        await callback.answer(f"Проект '{name}' не найден", show_alert=True)
        return
    log.info("Меню: проект выбран %s", name)

    text = _menu_text(storage, uid)
    markup = _main_menu_markup(storage, uid, settings)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer(f"Проект: {name}")


# ── Проекты: новый (FSM) ──

@router.callback_query(F.data == "p:new")
async def cb_new_project(
    callback: CallbackQuery, state: FSMContext,
) -> None:
    await callback.message.edit_text(
        "Введи название проекта (a-z, 0-9, -, _, макс 32):"
    )
    await state.set_state(CreateProject.waiting_name)
    await callback.answer()


@router.message(CreateProject.waiting_name)
async def process_project_name(
    message: Message, state: FSMContext, storage: SessionStorage, settings: Settings,
) -> None:
    name = message.text.strip() if message.text else ""
    if not re.match(r"^[a-zA-Z0-9_-]{1,32}$", name):
        await message.answer(
            "Недопустимое имя. Используй a-z, 0-9, -, _ (макс 32 символа)."
        )
        return

    uid = message.from_user.id
    projects_dir = get_user_projects_dir(settings, uid)
    await storage.create_project(uid, name, projects_dir)
    log.info("Меню: проект создан %s", name)
    await state.clear()

    text = _menu_text(storage, uid)
    markup = _main_menu_markup(storage, uid, settings)
    await message.answer(f"Проект '{name}' создан.\n\n{text}", reply_markup=markup)


# ── Сессии: полный список ──

@router.callback_query(F.data.startswith("s:list:"))
async def cb_session_list(callback: CallbackQuery, storage: SessionStorage) -> None:
    uid = callback.from_user.id
    page = int(callback.data.split(":")[2])
    sessions = storage.get_all_sessions(uid)
    active_id = storage.get_active_session_id(uid)

    items = []
    for s in sessions:
        label = f">> {s.name}" if s.id == active_id else s.name
        items.append((label, f"s:sel:{s.id[:50]}"))

    text = "Sessions:" if items else "Sessions: (пусто)"
    markup = build_paginated_keyboard(
        items=items,
        page=page,
        new_callback="s:new",
        back_callback="m:main",
        more_prefix="s:list:",
    )
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer()


# ── Сессии: выбор ──

@router.callback_query(F.data.startswith("s:sel:"))
async def cb_select_session(callback: CallbackQuery, storage: SessionStorage, settings: Settings) -> None:
    uid = callback.from_user.id
    sid = callback.data[6:]  # после "s:sel:"
    ok = await storage.set_active_session(uid, sid)
    if not ok:
        await callback.answer("Сессия не найдена", show_alert=True)
        return
    log.info("Меню: сессия выбрана %s", sid[:8])

    text = _menu_text(storage, uid)
    markup = _main_menu_markup(storage, uid, settings)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer("Сессия переключена")


# ── Сессии: новая ──

@router.callback_query(F.data == "s:new")
async def cb_new_session(callback: CallbackQuery, storage: SessionStorage, settings: Settings) -> None:
    uid = callback.from_user.id
    await storage.create_new_session(uid)
    log.info("Меню: новая сессия")

    text = _menu_text(storage, uid)
    markup = _main_menu_markup(storage, uid, settings)
    await callback.message.edit_text(text, reply_markup=markup)
    await callback.answer("Новая сессия создана")


# ── Заглушка ──

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()
