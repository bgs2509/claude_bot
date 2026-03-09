"""Обработчики команд бота."""

import logging
from datetime import date

from aiogram import Router
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.services.claude import MODELS, get_project_dir
from claude_bot.services.storage import SessionStorage
from claude_bot.state import AppState

router = Router(name="commands")
log = logging.getLogger("claude-bot.commands")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    log.info("Команда /start")
    await message.answer(
        "Claude Code Bot\n\n"
        "Что умею:\n"
        "• Текст, голос, фото, файлы → Claude ответит\n"
        "• Работаю с кодом, файловой системой, bash\n"
        "• Проекты и сессии — /menu\n\n"
        "/help — полная справка и все команды"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    log.info("Команда /help")
    await message.answer(
        "📖 <b>Как пользоваться ботом</b>\n\n"

        "<b>Что можно отправлять:</b>\n"
        "• Текст — любой вопрос или задача\n"
        "• Голосовое — распознается и обработается\n"
        "• Фото — текст извлечётся через OCR\n"
        "• Файл — сохраняется в проект, анализируется Claude\n\n"

        "<b>Команды бота:</b>\n"
        "/menu — проекты и сессии\n"
        "/new — новая сессия (сбросить контекст)\n"
        "/cancel — отменить текущий запрос\n"
        "/model — сменить модель (haiku / sonnet / opus)\n"
        "/voice — вкл/выкл голосовые ответы\n"
        "/status — текущее состояние\n"
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
        '📖 <a href="https://github.com/bgs2509/claude_bot/blob/master/docs/USAGE.md">Полная документация</a>',
        parse_mode="HTML",
    )


@router.message(Command("new"))
async def cmd_new(
    message: Message, app_state: AppState, storage: SessionStorage | None = None,
) -> None:
    uid = message.from_user.id
    log.info("Команда /new — сброс сессии")
    app_state.user_sessions.pop(uid, None)
    if storage:
        await storage.create_new_session(uid)
    await message.answer("Сессия сброшена. Следующее сообщение начнёт новую.")


@router.message(Command("cancel"))
async def cmd_cancel(
    message: Message, app_state: AppState, state: FSMContext,
) -> None:
    uid = message.from_user.id
    # Сбросить FSM-состояние если активно
    current_state = await state.get_state()
    if current_state:
        await state.clear()
        await message.answer("Действие отменено.")
        return

    proc = app_state.active_processes.pop(uid, None)
    if proc:
        proc.kill()
        log.info("Команда /cancel — killed")
        await message.answer("Запрос отменён.")
    else:
        log.info("Команда /cancel — нет процесса")
        await message.answer("Нет активного запроса.")


@router.message(Command("model"))
async def cmd_model(message: Message, command: CommandObject, app_state: AppState, role: str) -> None:
    if role != "admin":
        await message.answer("Только для admin.")
        return

    uid = message.from_user.id
    args = command.args

    if not args:
        current = app_state.user_models.get(uid, "sonnet")
        names = " | ".join(MODELS.keys())
        await message.answer(f"Модель: {current}\nДоступные: {names}")
        return

    name = args.strip().lower()
    if name not in MODELS:
        await message.answer(f"Неизвестная модель. Доступные: {' | '.join(MODELS.keys())}")
        return

    app_state.user_models[uid] = name
    log.info("Команда /model: %s", name)
    await message.answer(f"Модель: {name}")


@router.message(Command("voice"))
async def cmd_voice(message: Message, app_state: AppState) -> None:
    uid = message.from_user.id
    current = app_state.user_voice_mode.get(uid, False)
    app_state.user_voice_mode[uid] = not current
    status = "включён" if not current else "выключен"
    log.info("Команда /voice: %s", status)
    await message.answer(f"Голосовой режим {status}")


@router.message(Command("status"))
async def cmd_status(
    message: Message,
    app_state: AppState,
    settings: Settings,
    storage: SessionStorage | None = None,
) -> None:
    log.info("Команда /status")
    uid = message.from_user.id
    # Определить актуальную модель с учётом конфига
    user_cfg = settings.users.get(str(uid))
    user_role = user_cfg.get("role", "readonly") if user_cfg else "readonly"
    config_model = user_cfg.get("model") if user_cfg else None
    if user_role == "user" and config_model:
        model = config_model
    elif config_model:
        model = app_state.user_models.get(uid, config_model)
    else:
        model = app_state.user_models.get(uid, "sonnet")
    voice = "вкл" if app_state.user_voice_mode.get(uid, False) else "выкл"
    cwd = str(get_project_dir(settings, storage, uid))

    project_name = "—"
    session_name = "—"
    if storage:
        user = storage.get_user(uid)
        project_name = user.active_project or "—"
        pd = storage._get_project_data(uid)
        if pd.active_session:
            for s in pd.sessions:
                if s.id == pd.active_session:
                    session_name = s.name
                    break

    await message.answer(
        f"Проект: {project_name}\n"
        f"Сессия: {session_name}\n"
        f"Модель: {model}\n"
        f"Голос: {voice}\n"
        f"Директория: {cwd}"
    )


@router.message(Command("usage"))
async def cmd_usage(message: Message, settings: Settings, app_state: AppState) -> None:
    log.info("Команда /usage")
    uid = message.from_user.id
    count_data = app_state.user_daily_count.get(uid, {})
    today = date.today().isoformat()
    today_count = (
        count_data.get("count", 0)
        if count_data.get("date") == today
        else 0
    )

    await message.answer(f"Сегодня: {today_count} сообщений")


@router.message(Command("stats"))
async def cmd_stats(message: Message, settings: Settings, app_state: AppState, role: str) -> None:
    log.info("Команда /stats")
    if role != "admin":
        await message.answer("Только для admin.")
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

    await message.answer("\n".join(lines))
