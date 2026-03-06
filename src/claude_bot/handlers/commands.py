"""Обработчики команд бота."""

from datetime import date

from aiogram import Router
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.services.claude import MODELS
from claude_bot.state import AppState

router = Router(name="commands")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    await message.answer(
        "Claude Code Bot\n\n"
        "Отправь текст, голосовое или фото — Claude ответит.\n\n"
        "/help — справка и список команд"
    )


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(
        "📖 <b>Как пользоваться ботом</b>\n\n"

        "<b>Что можно отправлять:</b>\n"
        "• Текст — любой вопрос или задача\n"
        "• Голосовое — распознается и обработается\n"
        "• Фото — текст извлечётся через OCR\n"
        "• Файл — содержимое будет прочитано\n\n"

        "<b>Команды бота:</b>\n"
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
        "📖 Полная документация: docs/USAGE.md",
        parse_mode="HTML",
    )


@router.message(Command("new"))
async def cmd_new(message: Message, state: AppState) -> None:
    uid = message.from_user.id
    state.user_sessions.pop(uid, None)
    await message.answer("Сессия сброшена. Следующее сообщение начнёт новую.")


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: AppState) -> None:
    uid = message.from_user.id
    proc = state.active_processes.pop(uid, None)
    if proc:
        proc.kill()
        await message.answer("Запрос отменён.")
    else:
        await message.answer("Нет активного запроса.")


@router.message(Command("model"))
async def cmd_model(message: Message, command: CommandObject, state: AppState) -> None:
    uid = message.from_user.id
    args = command.args

    if not args:
        current = state.user_models.get(uid, "sonnet")
        names = " | ".join(MODELS.keys())
        await message.answer(f"Модель: {current}\nДоступные: {names}")
        return

    name = args.strip().lower()
    if name not in MODELS:
        await message.answer(f"Неизвестная модель. Доступные: {' | '.join(MODELS.keys())}")
        return

    state.user_models[uid] = name
    await message.answer(f"Модель: {name}")


@router.message(Command("voice"))
async def cmd_voice(message: Message, state: AppState) -> None:
    uid = message.from_user.id
    current = state.user_voice_mode.get(uid, False)
    state.user_voice_mode[uid] = not current
    status = "включён" if not current else "выключен"
    await message.answer(f"Голосовой режим {status}")


@router.message(Command("status"))
async def cmd_status(message: Message, state: AppState, settings: Settings) -> None:
    uid = message.from_user.id
    model = state.user_models.get(uid, "sonnet")
    session = state.user_sessions.get(uid, "нет")
    voice = "вкл" if state.user_voice_mode.get(uid, False) else "выкл"
    cwd = str(settings.projects_dir)

    await message.answer(
        f"Модель: {model}\n"
        f"Сессия: {session}\n"
        f"Голос: {voice}\n"
        f"Директория: {cwd}"
    )


@router.message(Command("usage"))
async def cmd_usage(message: Message, settings: Settings, state: AppState) -> None:
    uid = message.from_user.id
    count_data = state.user_daily_count.get(uid, {})
    today = date.today().isoformat()
    today_count = (
        count_data.get("count", 0)
        if count_data.get("date") == today
        else 0
    )

    cfg = settings.users.get(str(uid))
    limit = cfg.get("limit", 0) if cfg else 0
    limit_str = str(limit) if limit else "∞"

    await message.answer(f"Сегодня: {today_count} / {limit_str} сообщений")


@router.message(Command("stats"))
async def cmd_stats(message: Message, settings: Settings, state: AppState, role: str) -> None:
    if role != "admin":
        await message.answer("Только для admin.")
        return

    lines = ["Статистика:\n"]
    for user_id_str, cfg in settings.users.items():
        name = cfg.get("name", user_id_str)
        user_role = cfg.get("role", "?")
        count_data = state.user_daily_count.get(int(user_id_str), {})
        today_count = (
            count_data.get("count", 0)
            if count_data.get("date") == date.today().isoformat()
            else 0
        )
        limit = cfg.get("limit", 0)
        limit_str = f"{today_count}/{limit}" if limit else f"{today_count}/∞"
        lines.append(f"  {name} ({user_role}): {limit_str} сегодня")

    await message.answer("\n".join(lines))
