"""Обработчики команд бота."""

import html as html_lib
import logging
import re
import zoneinfo
from datetime import date, datetime, timedelta
from pathlib import Path

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from ai_steward.config import Settings, get_user_projects_dir
from ai_steward.constants import (
    CATEGORY_EMOJI,
    DAY_NAMES_RU,
    EMOJI_ACTIVE,
    EMOJI_HOME,
    EMOJI_INACTIVE,
    EMOJI_REMINDER,
    NOTIFY_DESC_PREVIEW_LEN,
    PLAN_CB_DAY,
    PLAN_CB_WEEK,
)
from ai_steward.errors import InfrastructureError, get_user_message
from ai_steward.handlers import _build_reply_kb
from ai_steward.keyboards import (
    build_paginated_keyboard,
    build_plan_keyboard,
    build_sessions_keyboard,
    build_status_keyboard,
)
from ai_steward.models.notification import Notification
from ai_steward.models.planner import PlanItem
from ai_steward.services import notification_service as ns
from ai_steward.services import planner_service as pls
from ai_steward.services.claude import MODELS, get_project_dir
from ai_steward.services.planner_formatter import (
    format_day_plan,
    format_week_overview,
)
from ai_steward.services.storage import SessionStorage
from ai_steward.state import AppState

router = Router(name="commands")
log = logging.getLogger("ai-steward.commands")


# ── FSM для создания проекта ──

class CreateProject(StatesGroup):
    waiting_name = State()


# ── Хелперы ──

def _status_text(
    storage: SessionStorage | None,
    uid: int,
    app_state: AppState,
    settings: Settings,
) -> str:
    """Текст статуса: проект · сессия, модель · голос."""
    # Проект и сессия
    if storage:
        user = storage.get_user(uid)
        project_name = user.active_project
        session_name = storage.get_active_session_name(uid)
    else:
        project_name = None
        session_name = None

    if project_name:
        line_project = f"📂 Проект: {project_name}"
        line_session = f"💬 Сессия: {session_name}" if session_name else ""
    else:
        line_project = f"{EMOJI_HOME} Проект: Общий"
        line_session = f"💬 Сессия: {session_name}" if session_name else ""

    # Модель и голос
    user_cfg = settings.users.get(str(uid))
    config_model = user_cfg.get("model") if user_cfg else None
    user_role = user_cfg.get("role", "readonly") if user_cfg else "readonly"
    if user_role == "user" and config_model:
        model = config_model
    elif config_model:
        model = app_state.user_models.get(uid, config_model)
    else:
        model = app_state.user_models.get(uid, "sonnet")
    voice = "вкл" if app_state.user_voice_mode.get(uid, False) else "выкл"
    line_settings = f"🤖 Модель: {model} · 🔇 Голос: {voice}"

    lines = [line_project]
    if line_session:
        lines.append(line_session)
    lines.append(line_settings)
    return "\n".join(lines)


# ── /start ──

@router.message(CommandStart())
async def cmd_start(
    message: Message, settings: Settings, storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    log.info("Команда /start")
    uid = message.from_user.id
    reply_kb = _build_reply_kb(storage, settings, uid)
    await message.answer(
        project_tag +
        "Claude Code Bot\n\n"
        "Что умею:\n"
        "• Текст, голос, фото, файлы → Claude ответит\n"
        "• Работаю с кодом, файловой системой, bash\n"
        "• Проекты и сессии — /status\n\n"
        "/help — полная справка и все команды",
        parse_mode="HTML",
        reply_markup=reply_kb,
    )


# ── /help ──

@router.message(Command("help"))
async def cmd_help(message: Message, project_tag: str = "") -> None:
    log.info("Команда /help")
    await message.answer(
        project_tag +
        "📖 <b>Как пользоваться ботом</b>\n\n"

        "<b>Что можно отправлять:</b>\n"
        "• Текст — любой вопрос или задача\n"
        "• Голосовое — распознается и обработается\n"
        "• Фото — текст извлечётся через OCR\n"
        "• Файл — сохраняется в проект, анализируется Claude\n\n"

        "<b>Команды бота:</b>\n"
        "/status — проекты, сессии, настройки\n"
        "/new — новая сессия (сбросить контекст)\n"
        "/cancel — отменить текущий запрос\n"
        "/model — сменить модель (haiku / sonnet / opus)\n"
        "/voice — вкл/выкл голосовые ответы\n"
        "/usage — твоя статистика за сегодня\n"
        "/stats — статистика всех (admin)\n\n"

        "<b>Навигация и bash:</b>\n"
        "Claude понимает любые команды прямо в чате:\n"
        "• <code>ls</code> — список файлов\n"
        "• <code>cd my-project</code> — перейти в проект\n"
        "• <code>mkdir new-project && cd new-project</code>\n"
        "• <code>pwd</code> — текущая директория\n"
        "• <code>git init</code>, <code>git status</code>, ...\n\n"

        "Или на естественном языке:\n"
        "• «создай папку my-app и перейди в неё»\n"
        "• «покажи содержимое текущей директории»\n\n"

        "<b>Контекст</b> сохраняется между сообщениями. "
        "/new — сбросить.\n\n"
        '📖 <a href="https://github.com/bgs2509/ai-steward/blob/master/docs/USAGE.md">Полная документация</a>',
        parse_mode="HTML",
    )


# ── /new ──

@router.message(Command("new"))
async def cmd_new(
    message: Message, app_state: AppState, storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    uid = message.from_user.id
    log.info("Команда /new — сброс сессии")

    session_name = storage.get_active_session_name(uid) if storage else None
    app_state.user_sessions.pop(uid, None)
    if storage:
        await storage.create_new_session(uid)

    if session_name:
        await message.answer(
            project_tag + f"Сессия «{session_name}» сброшена. Следующее сообщение начнёт новую.",
            parse_mode="HTML",
        )
    else:
        await message.answer(project_tag + "Сессия сброшена. Следующее сообщение начнёт новую.", parse_mode="HTML")


# ── /cancel ──

@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message, app_state: AppState, state: FSMContext,
    project_tag: str = "",
) -> None:
    uid = message.from_user.id
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer(project_tag + "Действие отменено.", parse_mode="HTML")
        return

    proc = app_state.active_processes.pop(uid, None)
    if proc:
        proc.kill()
        log.info("Команда /cancel — killed")
        await message.answer(project_tag + "Запрос отменён.", parse_mode="HTML")
    else:
        log.info("Команда /cancel — нет процесса")
        await message.answer(project_tag + "Нет активного запроса.", parse_mode="HTML")


# ── /model ──

@router.message(Command("model"))
async def cmd_model(message: Message, command: CommandObject, app_state: AppState, role: str, project_tag: str = "") -> None:
    if role != "admin":
        await message.answer(project_tag + "Только для admin.", parse_mode="HTML")
        return

    uid = message.from_user.id
    args = command.args

    if not args:
        current = app_state.user_models.get(uid, "sonnet")
        names = " | ".join(MODELS.keys())
        await message.answer(project_tag + f"Модель: {current}\nДоступные: {names}", parse_mode="HTML")
        return

    name = args.strip().lower()
    if name not in MODELS:
        await message.answer(project_tag + f"Неизвестная модель. Доступные: {' | '.join(MODELS.keys())}", parse_mode="HTML")
        return

    app_state.user_models[uid] = name
    log.info("Команда /model: %s", name)
    await message.answer(project_tag + f"Модель: {name}", parse_mode="HTML")


# ── /voice ──

@router.message(Command("voice"))
async def cmd_voice(message: Message, app_state: AppState, project_tag: str = "") -> None:
    uid = message.from_user.id
    current = app_state.user_voice_mode.get(uid, False)
    app_state.user_voice_mode[uid] = not current
    status = "включён" if not current else "выключен"
    log.info("Команда /voice: %s", status)
    await message.answer(project_tag + f"Голосовой режим {status}", parse_mode="HTML")


# ── /status ──

@router.message(Command("status"))
async def cmd_status(
    message: Message,
    app_state: AppState,
    settings: Settings,
    storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    log.info("Команда /status")
    uid = message.from_user.id
    text = _status_text(storage, uid, app_state, settings)

    if storage:
        projects_dir = get_user_projects_dir(settings, uid)
        projects = storage.list_projects(projects_dir)
        user = storage.get_user(uid)

        if not projects:
            text += "\n\nОтправь сообщение — бот работает в общей директории.\nИли создай проект:"

        markup = build_status_keyboard(projects, user.active_project)
        await message.answer(project_tag + text, parse_mode="HTML", reply_markup=markup)
    else:
        await message.answer(project_tag + text, parse_mode="HTML")


# ── /status callback: главный экран ──

@router.callback_query(F.data == "st:main")
async def cb_status_main(
    callback: CallbackQuery,
    app_state: AppState,
    settings: Settings,
    storage: SessionStorage,
) -> None:
    uid = callback.from_user.id
    user = storage.get_user(uid)
    tag = f"<code>[{user.active_project or 'Общий'}]</code>\n\n"
    text = _status_text(storage, uid, app_state, settings)
    projects_dir = get_user_projects_dir(settings, uid)
    projects = storage.list_projects(projects_dir)

    if not projects:
        text += "\n\nОтправь сообщение — бот работает в общей директории.\nИли создай проект:"

    markup = build_status_keyboard(projects, user.active_project)
    await callback.message.edit_text(tag + text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


# ── /status callback: выбор проекта → показать сессии ──

@router.callback_query(F.data.startswith("st:proj:"))
async def cb_status_project(
    callback: CallbackQuery,
    settings: Settings,
    storage: SessionStorage,
) -> None:
    uid = callback.from_user.id
    project_name = callback.data[8:]  # после "st:proj:"
    projects_dir = get_user_projects_dir(settings, uid)
    ok = await storage.set_active_project(uid, project_name, projects_dir)
    if not ok:
        await callback.answer(f"Проект '{project_name}' не найден", show_alert=True)
        return
    log.info("Status: проект выбран %s", project_name)
    tag = f"<code>[{project_name}]</code>\n\n"
    sessions = storage.get_project_sessions(uid, project_name)
    active_sid = storage.get_project_active_session_id(uid, project_name)

    items = [(s.name, s.id) for s in sessions]
    text = f"{EMOJI_INACTIVE} {project_name}" if sessions else f"{EMOJI_INACTIVE} {project_name}\n\nСессий пока нет."
    markup = build_sessions_keyboard(items, active_sid)
    await callback.message.edit_text(tag + text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


# ── /status callback: выбор сессии ──

@router.callback_query(F.data.startswith("st:ssel:"))
async def cb_status_select_session(
    callback: CallbackQuery,
    app_state: AppState,
    settings: Settings,
    storage: SessionStorage,
) -> None:
    uid = callback.from_user.id
    sid = callback.data[8:]  # после "st:ssel:"
    ok = await storage.set_active_session(uid, sid)
    if not ok:
        await callback.answer("Сессия не найдена", show_alert=True)
        return
    log.info("Status: сессия выбрана %s", sid[:8])

    # Вернуться на главный экран статуса
    user = storage.get_user(uid)
    tag = f"<code>[{user.active_project or 'Общий'}]</code>\n\n"
    text = _status_text(storage, uid, app_state, settings)
    projects_dir = get_user_projects_dir(settings, uid)
    projects = storage.list_projects(projects_dir)
    markup = build_status_keyboard(projects, user.active_project)
    await callback.message.edit_text(tag + text, parse_mode="HTML", reply_markup=markup)
    await callback.answer("Сессия переключена")


# ── /status callback: пагинация сессий ──

@router.callback_query(F.data.startswith("st:sess:"))
async def cb_status_sessions_page(
    callback: CallbackQuery,
    settings: Settings,
    storage: SessionStorage,
) -> None:
    uid = callback.from_user.id
    page = int(callback.data.split(":")[2])
    user = storage.get_user(uid)
    project_name = user.active_project or "__global__"
    tag = f"<code>[{user.active_project or 'Общий'}]</code>\n\n"
    sessions = storage.get_project_sessions(uid, project_name)
    active_sid = storage.get_project_active_session_id(uid, project_name)

    items = [(s.name, s.id) for s in sessions]
    text = f"{EMOJI_INACTIVE} {project_name}"
    markup = build_sessions_keyboard(items, active_sid, page=page)
    await callback.message.edit_text(tag + text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


# ── /status callback: новая сессия ──

@router.callback_query(F.data == "st:newsess")
async def cb_status_new_session(
    callback: CallbackQuery,
    app_state: AppState,
    settings: Settings,
    storage: SessionStorage,
) -> None:
    uid = callback.from_user.id
    await storage.create_new_session(uid)
    app_state.user_sessions.pop(uid, None)
    log.info("Status: новая сессия")

    user = storage.get_user(uid)
    tag = f"<code>[{user.active_project or 'Общий'}]</code>\n\n"
    text = _status_text(storage, uid, app_state, settings)
    projects_dir = get_user_projects_dir(settings, uid)
    projects = storage.list_projects(projects_dir)
    markup = build_status_keyboard(projects, user.active_project)
    await callback.message.edit_text(tag + text, parse_mode="HTML", reply_markup=markup)
    await callback.answer("Новая сессия создана")


# ── /status callback: домой (сбросить проект) ──

@router.callback_query(F.data == "st:home")
async def cb_status_home(
    callback: CallbackQuery,
    app_state: AppState,
    settings: Settings,
    storage: SessionStorage,
) -> None:
    uid = callback.from_user.id
    await storage.clear_active_project(uid)
    log.info("Status: сброс проекта")

    tag = "<code>[Общий]</code>\n\n"
    # Показать сессии __global__ (единообразно с проектами)
    sessions = storage.get_project_sessions(uid, "__global__")
    active_sid = storage.get_project_active_session_id(uid, "__global__")
    items = [(s.name, s.id) for s in sessions]
    text = f"{EMOJI_HOME} Общий"
    if not sessions:
        text += "\n\nСессий пока нет."
    markup = build_sessions_keyboard(items, active_sid)
    await callback.message.edit_text(tag + text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


# ── /status callback: создать проект (FSM) ──

@router.callback_query(F.data == "st:newproj")
async def cb_status_new_project(
    callback: CallbackQuery, state: FSMContext, project_tag: str = "",
) -> None:
    await callback.message.edit_text(
        project_tag + "Введи название проекта (a-z, 0-9, -, _, макс 32):",
        parse_mode="HTML",
    )
    await state.set_state(CreateProject.waiting_name)
    await callback.answer()


# ── /status callback: пагинация проектов ──

@router.callback_query(F.data.startswith("p:list:"))
async def cb_project_list(
    callback: CallbackQuery, storage: SessionStorage, settings: Settings,
    project_tag: str = "",
) -> None:
    uid = callback.from_user.id
    page = int(callback.data.split(":")[2])
    projects_dir = get_user_projects_dir(settings, uid)
    projects = storage.list_projects(projects_dir)
    active = storage.get_user(uid).active_project

    items = []
    for name in projects:
        emoji = EMOJI_ACTIVE if name == active else EMOJI_INACTIVE
        items.append((f"{emoji} {name}", f"p:sel:{name[:50]}"))

    markup = build_paginated_keyboard(
        items=items, page=page,
        new_callback="st:newproj",
        back_callback="st:main",
        more_prefix="p:list:",
    )
    await callback.message.edit_text(project_tag + "Проекты:", parse_mode="HTML", reply_markup=markup)
    await callback.answer()


# ── /status callback: выбор проекта из пагинации ──

@router.callback_query(F.data.startswith("p:sel:"))
async def cb_select_project(
    callback: CallbackQuery,
    app_state: AppState,
    settings: Settings,
    storage: SessionStorage,
) -> None:
    uid = callback.from_user.id
    name = callback.data[6:]  # после "p:sel:"
    projects_dir = get_user_projects_dir(settings, uid)
    ok = await storage.set_active_project(uid, name, projects_dir)
    if not ok:
        await callback.answer(f"Проект '{name}' не найден", show_alert=True)
        return
    log.info("Status: проект выбран %s", name)

    # Пересчитать тег после смены проекта
    tag = f"<code>[{name}]</code>\n\n"
    # Показать сессии выбранного проекта
    sessions = storage.get_project_sessions(uid, name)
    active_sid = storage.get_project_active_session_id(uid, name)
    items = [(s.name, s.id) for s in sessions]
    text = f"{EMOJI_INACTIVE} {name}" if sessions else f"{EMOJI_INACTIVE} {name}\n\nСессий пока нет."
    markup = build_sessions_keyboard(items, active_sid)
    await callback.message.edit_text(tag + text, parse_mode="HTML", reply_markup=markup)
    await callback.answer(f"Проект: {name}")


# ── FSM: ввод имени проекта ──

@router.message(CreateProject.waiting_name)
async def process_project_name(
    message: Message, state: FSMContext, storage: SessionStorage, settings: Settings,
    app_state: AppState, project_tag: str = "",
) -> None:
    name = message.text.strip() if message.text else ""
    if not re.match(r"^[a-zA-Z0-9_-]{1,32}$", name):
        await message.answer(
            project_tag + "Недопустимое имя. Используй a-z, 0-9, -, _ (макс 32 символа).",
            parse_mode="HTML",
        )
        return

    uid = message.from_user.id
    projects_dir = get_user_projects_dir(settings, uid)
    await storage.create_project(uid, name, projects_dir)
    log.info("Status: проект создан %s", name)
    await state.clear()

    # Пересчитать тег — теперь активный проект изменился
    tag = f"<code>[{name}]</code>\n\n"
    reply_kb = _build_reply_kb(storage, settings, uid)
    text = _status_text(storage, uid, app_state, settings)
    projects = storage.list_projects(projects_dir)
    user = storage.get_user(uid)
    markup = build_status_keyboard(projects, user.active_project)
    await message.answer(
        tag + f"Проект '{name}' создан.\n\n{text}",
        parse_mode="HTML",
        reply_markup=reply_kb,
    )
    await message.answer(tag + "Проекты:", parse_mode="HTML", reply_markup=markup)


# ── /status callback: заглушка ──

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery) -> None:
    await callback.answer()


# ── /plan ──


def _now_local(settings: Settings) -> datetime:
    """Текущее время в часовом поясе планировщика."""
    tz = zoneinfo.ZoneInfo(settings.notify_timezone)
    return datetime.now(tz)


@router.message(Command("plan"))
async def cmd_plan(
    message: Message,
    command: CommandObject,
    settings: Settings,
    storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    """Показать план на сегодня с навигацией по дням."""
    log.info("Команда /plan")
    uid = message.from_user.id
    args = command.args or ""

    now = _now_local(settings)
    today = now.date()

    # Собрать все проекты пользователя
    projects_dir = get_user_projects_dir(settings, uid)
    all_items = _collect_plan_items(projects_dir, storage, today)

    # Фильтр по категории
    category_filter = args.strip().lower() if args.strip() else None
    if category_filter:
        all_items = [i for i in all_items if i.category == category_filter]

    text = format_day_plan(today, all_items, now)
    markup = build_plan_keyboard(today)
    await message.answer(
        project_tag + text,
        parse_mode="HTML",
        reply_markup=markup,
    )


@router.callback_query(F.data.startswith(PLAN_CB_DAY))
async def cb_plan_day(
    callback: CallbackQuery,
    settings: Settings,
    storage: SessionStorage | None = None,
) -> None:
    """Навигация по дням: показать план на выбранную дату."""
    uid = callback.from_user.id
    date_str = callback.data[len(PLAN_CB_DAY):]
    try:
        d = date.fromisoformat(date_str)
    except ValueError:
        await callback.answer("Некорректная дата", show_alert=True)
        return

    now = _now_local(settings)

    projects_dir = get_user_projects_dir(settings, uid)
    items = _collect_plan_items(projects_dir, storage, d)

    text = format_day_plan(d, items, now)
    markup = build_plan_keyboard(d)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == PLAN_CB_WEEK)
async def cb_plan_week(
    callback: CallbackQuery,
    settings: Settings,
    storage: SessionStorage | None = None,
) -> None:
    """Обзор текущей недели."""
    uid = callback.from_user.id

    now = _now_local(settings)
    today = now.date()

    # Понедельник текущей недели
    monday = today - timedelta(days=today.weekday())
    projects_dir = get_user_projects_dir(settings, uid)

    days: dict[date, list[PlanItem]] = {}
    for offset in range(7):
        d = monday + timedelta(days=offset)
        days[d] = _collect_plan_items(projects_dir, storage, d)

    text = format_week_overview(days, now)
    # Кнопка «назад к сегодня»
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="📅 Сегодня",
            callback_data=f"{PLAN_CB_DAY}{today.isoformat()}",
        )],
    ])
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()


def _collect_plan_items(
    projects_dir: Path,
    storage: SessionStorage | None,
    d: date,
) -> list[PlanItem]:
    """Собрать элементы плана из всех проектов пользователя на дату."""
    all_items: list[PlanItem] = []

    # __global__
    global_dir = projects_dir / "__global__"
    if global_dir.is_dir():
        try:
            all_items.extend(pls.get_by_date(global_dir, d))
        except InfrastructureError as e:
            log.warning("plan: ошибка чтения __global__: %s", e)

    # Обычные проекты
    if storage:
        for name in storage.list_projects(projects_dir):
            try:
                all_items.extend(pls.get_by_date(projects_dir / name, d))
            except InfrastructureError as e:
                log.warning("plan: ошибка чтения %s: %s", name, e)

    return all_items


# ── /notify (алиас для /plan) ──

@router.message(Command("notify"))
async def cmd_notify(
    message: Message,
    command: CommandObject,
    settings: Settings,
    storage: SessionStorage | None = None,
    project_tag: str = "",
) -> None:
    log.info("Команда /notify")
    uid = message.from_user.id
    args = command.args or ""

    projects_dir = get_user_projects_dir(settings, uid)

    if args.strip() == "all":
        # Все проекты
        all_notifications: list[tuple[str, list]] = []
        # __global__
        global_dir = projects_dir / "__global__"
        if global_dir.is_dir():
            try:
                active = ns.get_active(global_dir)
                if active:
                    all_notifications.append(("Общий", active))
            except InfrastructureError as e:
                log.warning("notify: ошибка чтения __global__: %s", e)
        # Обычные проекты
        if storage:
            for name in storage.list_projects(projects_dir):
                try:
                    active = ns.get_active(projects_dir / name)
                    if active:
                        all_notifications.append((name, active))
                except InfrastructureError as e:
                    log.warning("notify: ошибка чтения %s: %s", name, e)

        if not all_notifications:
            await message.answer(project_tag + get_user_message("notify_empty"), parse_mode="HTML")
            return

        text = f"{EMOJI_REMINDER} <b>Все уведомления</b>\n"
        for proj_name, notifications in all_notifications:
            text += f"\n<b>📂 {proj_name}</b>\n"
            text += _format_notify_list(notifications)
        await message.answer(project_tag + text, parse_mode="HTML")
    else:
        # Текущий проект
        if storage:
            user = storage.get_user(uid)
            project_name = user.active_project
        else:
            project_name = None

        if project_name:
            project_path = projects_dir / project_name
            label = project_name
        else:
            project_path = projects_dir / "__global__"
            label = "Общий"

        try:
            notifications = ns.get_active(project_path)
        except InfrastructureError as e:
            log.warning("notify: ошибка чтения %s: %s", project_path, e)
            notifications = []

        if not notifications:
            await message.answer(project_tag + get_user_message("notify_empty"), parse_mode="HTML")
            return

        text = (
            f"{EMOJI_REMINDER} <b>Уведомления — {label}</b>\n\n"
            + _format_notify_list(notifications)
        )
        await message.answer(project_tag + text, parse_mode="HTML")


def _format_notify_list(notifications: list[Notification]) -> str:
    """Форматировать список уведомлений в HTML."""
    lines = []
    for n in notifications:
        emoji = CATEGORY_EMOJI.get(n.category, EMOJI_REMINDER)
        title = html_lib.escape(n.title)
        line = f"{emoji} <b>{title}</b>"

        # Расписание
        if n.repeat:
            if n.repeat.type == "daily":
                line += f"\nЕжедневно в {n.repeat.time}"
            elif n.repeat.type == "weekly":
                days_str = ", ".join(
                    DAY_NAMES_RU.get(d, d) for d in n.repeat.days
                )
                line += f"\nЕженедельно в {n.repeat.time} ({days_str})"
            elif n.repeat.type == "monthly":
                line += f"\nЕжемесячно {n.repeat.day}-го в {n.repeat.time}"
        else:
            dt = n.datetime
            line += f"\nОдноразовое — {dt.strftime('%d.%m.%Y %H:%M')}"

        if n.description:
            desc = html_lib.escape(n.description[:NOTIFY_DESC_PREVIEW_LEN])
            if len(n.description) > NOTIFY_DESC_PREVIEW_LEN:
                desc += "..."
            line += f"\n<i>{desc}</i>"

        lines.append(line)

    return "\n\n".join(lines)


# ── /usage ──

@router.message(Command("usage"))
async def cmd_usage(message: Message, settings: Settings, app_state: AppState, project_tag: str = "") -> None:
    log.info("Команда /usage")
    uid = message.from_user.id
    count_data = app_state.user_daily_count.get(uid, {})
    today = date.today().isoformat()
    today_count = (
        count_data.get("count", 0)
        if count_data.get("date") == today
        else 0
    )

    await message.answer(project_tag + f"Сегодня: {today_count} сообщений", parse_mode="HTML")


# ── /stats ──

@router.message(Command("stats"))
async def cmd_stats(message: Message, settings: Settings, app_state: AppState, role: str, project_tag: str = "") -> None:
    log.info("Команда /stats")
    if role != "admin":
        await message.answer(project_tag + "Только для admin.", parse_mode="HTML")
        return

    lines = ["Статистика:\n"]
    for user_id_str, cfg in settings.users.items():
        name = cfg.get("name", user_id_str)
        user_role = cfg.get("role", "?")
        count_data = app_state.user_daily_count.get(int(user_id_str), {})
        today_count = (
            count_data.get("count", 0)
            if count_data.get("date") == date.today().isoformat()
            else 0
        )
        limit = cfg.get("limit", 0)
        limit_str = f"{today_count}/{limit}" if limit else f"{today_count}/∞"
        lines.append(f"  {name} ({user_role}): {limit_str} сегодня")

    await message.answer(project_tag + "\n".join(lines), parse_mode="HTML")
