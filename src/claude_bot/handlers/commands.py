"""Обработчики команд бота."""

from datetime import date

from aiogram import Router
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message

from claude_bot.config import Settings
from claude_bot.state import AppState

router = Router(name="commands")


@router.message(CommandStart())
async def cmd_start(message: Message, settings: Settings, state: AppState, role: str) -> None:
    await message.answer(
        f"Claude Code Bot\n\n"
        f"Роль: {role}\n"
        f"Проект: {state.user_projects.get(message.from_user.id, '(по умолчанию)')}\n\n"
        f"Просто отправь текст, голосовое или фото.\n\n"
        f"Команды:\n"
        f"/new — новая сессия\n"
        f"/cancel — отменить запрос\n"
        f"/session — ID сессии\n"
        f"/project — список проектов\n"
        f"/project <имя> — переключить проект\n"
        f"/voice — вкл/выкл голосовые ответы\n"
        f"/stats — статистика (admin)"
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


@router.message(Command("session"))
async def cmd_session(message: Message, state: AppState) -> None:
    sid = state.user_sessions.get(message.from_user.id, "нет сессии")
    await message.answer(f"Session ID: {sid}")


@router.message(Command("project"))
async def cmd_project(message: Message, command: CommandObject, settings: Settings, state: AppState) -> None:
    uid = message.from_user.id
    args = command.args

    if not args:
        if not settings.projects_dir.exists():
            await message.answer(f"Директория проектов не найдена: {settings.projects_dir}")
            return
        projects = sorted(
            d.name for d in settings.projects_dir.iterdir() if d.is_dir()
        )
        if not projects:
            await message.answer(f"Нет проектов в {settings.projects_dir}")
            return

        current = state.user_projects.get(uid, "")
        lines = []
        for p in projects:
            marker = " ◀" if p == current else ""
            lines.append(f"  {p}{marker}")
        await message.answer(
            f"Проекты ({settings.projects_dir}):\n" + "\n".join(lines) +
            "\n\nПереключить: /project <имя>"
        )
        return

    # Переключить проект
    project_name = args.strip()
    project_path = settings.projects_dir / project_name
    if not project_path.exists():
        project_path.mkdir(parents=True, exist_ok=True)
        await message.answer(f"Создан и переключён на проект: {project_name}")
    else:
        await message.answer(f"Переключён на проект: {project_name}")

    state.user_projects[uid] = project_name
    # Сбросить сессию при смене проекта
    state.user_sessions.pop(uid, None)


@router.message(Command("voice"))
async def cmd_voice(message: Message, state: AppState) -> None:
    uid = message.from_user.id
    current = state.user_voice_mode.get(uid, False)
    state.user_voice_mode[uid] = not current
    status = "включён" if not current else "выключен"
    await message.answer(f"Голосовой режим {status}")


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
