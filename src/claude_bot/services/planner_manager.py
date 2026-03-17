"""Менеджер планировщика: фоновый цикл напоминаний, дайджестов и переноса задач."""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import re
import uuid
import zoneinfo
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramForbiddenError

from claude_bot.config import Settings, get_user_projects_dir
from claude_bot.constants import CATEGORY_EMOJI, EMOJI_REMINDER
from claude_bot.errors import InfrastructureError
from claude_bot.models.planner import PlanItem
from claude_bot.services import planner_service as ps
from claude_bot.services.planner_formatter import (
    format_evening_summary,
    format_morning_digest,
)

if TYPE_CHECKING:
    from aiogram import Bot
    from claude_bot.services.storage import SessionStorage

log = logging.getLogger("claude-bot.planner-manager")

# Допуск при проверке времени дайджестов (секунды)
_DIGEST_TOLERANCE = 90


class PlannerManager:
    """Фоновый сервис: напоминания, дайджесты, перенос задач."""

    def __init__(
        self,
        bot: Bot,
        settings: Settings,
        storage: SessionStorage,
    ) -> None:
        self.bot = bot
        self.settings = settings
        self.storage = storage
        self._task: asyncio.Task[None] | None = None
        self._first_scan_done = False
        self._morning_sent_date: date | None = None
        self._evening_sent_date: date | None = None

    async def init(self) -> None:
        """Запустить фоновый цикл сканирования."""
        self._task = asyncio.create_task(self._scan_loop())
        log.info(
            "PlannerManager запущен, интервал=%ds",
            self.settings.notify_scan_interval,
        )

    async def close(self) -> None:
        """Остановить фоновый цикл."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        log.info("PlannerManager остановлен")

    # ── Цикл сканирования ──

    async def _scan_loop(self) -> None:
        """Бесконечный цикл: проверка всех planner.json."""
        # Первый цикл — baseline (не отправлять, только запомнить)
        try:
            await self._scan_all(dry_run=True)
        except Exception:
            log.warning(
                "Ошибка первичного сканирования — работаем без baseline",
                exc_info=True,
            )
        self._first_scan_done = True

        while True:
            await asyncio.sleep(self.settings.notify_scan_interval)
            try:
                await self._scan_all(dry_run=False)
            except Exception:
                log.error("Ошибка цикла сканирования", exc_info=True)

    async def _scan_all(self, *, dry_run: bool = False) -> None:
        """Обойти всех пользователей и все их проекты."""
        tz = zoneinfo.ZoneInfo(self.settings.notify_timezone)
        now = datetime.now(tz)
        total_sent = 0

        # Дайджесты (раз в день, не в dry_run)
        if not dry_run:
            await self._check_digests(now)

        for uid_str, cfg in self.settings.users.items():
            uid = int(uid_str)
            try:
                projects_dir = get_user_projects_dir(self.settings, uid)
            except ValueError:
                continue

            project_dirs = self._get_all_project_dirs(uid, projects_dir)

            for project_path in project_dirs:
                try:
                    # Перенос незавершённых задач
                    if not dry_run:
                        self._carry_over(project_path, now)

                    sent = await self._check_project(
                        uid, project_path, now, dry_run=dry_run,
                        projects_dir=projects_dir,
                    )
                    total_sent += sent
                except InfrastructureError as e:
                    log.warning(
                        "Ошибка planner.json: uid=%d path=%s: %s",
                        uid, project_path, e,
                    )
                except Exception:
                    log.error(
                        "Неожиданная ошибка: uid=%d path=%s",
                        uid, project_path, exc_info=True,
                    )

        if total_sent > 0:
            log.info("Цикл сканирования: отправлено %d уведомлений", total_sent)

    def _get_all_project_dirs(
        self, uid: int, projects_dir: Path,
    ) -> list[Path]:
        """Все директории проектов пользователя, включая __global__."""
        dirs: list[Path] = []

        global_dir = projects_dir / "__global__"
        if global_dir.is_dir():
            dirs.append(global_dir)

        project_names = self.storage.list_projects(projects_dir)
        for name in project_names:
            dirs.append(projects_dir / name)

        return dirs

    # ── Напоминания ──

    async def _check_project(
        self,
        uid: int,
        project_path: Path,
        now: datetime,
        *,
        dry_run: bool = False,
        projects_dir: Path | None = None,
    ) -> int:
        """Проверить один проект, отправить все due-напоминания."""
        planner_path = project_path / ps.FILENAME
        if not planner_path.exists():
            # Попробовать миграцию
            old_path = project_path / ps.OLD_FILENAME
            if old_path.exists():
                ps.migrate_from_notify(project_path)
            elif not planner_path.exists():
                return 0

        items = ps.get_active(project_path)
        if not items:
            return 0

        sent_count = 0
        for item in items:
            due_minutes = ps.is_due(item, now)
            if not due_minutes:
                continue

            if dry_run:
                ps.mark_sent(project_path, item, due_minutes)
                continue

            # Тег проекта
            proj_name = project_path.name if project_path.name != "__global__" else "Общий"
            tag = f"<code>[{proj_name}]</code>\n\n"

            for minutes in due_minutes:
                text = _format_reminder(item, minutes)
                for recipient in item.recipients:
                    if str(recipient) not in self.settings.users:
                        log.warning(
                            "planner: recipient uid=%d не в allowlist",
                            recipient,
                        )
                        continue
                    await self._send(recipient, tag + text)

            ps.mark_sent(project_path, item, due_minutes)
            sent_count += 1

        return sent_count

    # ── Перенос незавершённых задач ──

    def _carry_over(self, project_path: Path, now: datetime) -> None:
        """Перенести pending/in_progress задачи из прошлых дней на сегодня."""
        today = now.date()
        try:
            data = ps.load(project_path)
        except InfrastructureError:
            return

        if data.last_carry_date == today:
            return  # Уже переносили сегодня

        yesterday = today - timedelta(days=1)
        to_carry = [
            item for item in data.items
            if item.date == yesterday
            and item.status in ("pending", "in_progress")
            and not item.repeat  # повторяющиеся не переносим
        ]

        if not to_carry:
            data.last_carry_date = today
            ps.save(project_path, data)
            return

        for item in to_carry:
            # Создать копию на сегодня
            new_item = item.model_copy(
                update={
                    "id": uuid.uuid4().hex[:12],
                    "date": today,
                    "carried_over": True,
                    "carried_from": yesterday,
                    "status": "pending",
                    "sent_reminders": [],
                },
            )
            data.items.append(new_item)

        data.last_carry_date = today
        ps.save(project_path, data)
        log.info(
            "Carry-over: %s — перенесено %d задач",
            project_path.name, len(to_carry),
        )

    # ── Дайджесты ──

    async def _check_digests(self, now: datetime) -> None:
        """Проверить нужно ли отправить утренний/вечерний дайджест."""
        today = now.date()

        # Утренний дайджест
        if (
            self.settings.plan_morning_time
            and self._morning_sent_date != today
            and self._is_digest_time(now, self.settings.plan_morning_time)
        ):
            await self._send_morning_digest(now)
            self._morning_sent_date = today

        # Вечерний дайджест
        if (
            self.settings.plan_evening_time
            and self._evening_sent_date != today
            and self._is_digest_time(now, self.settings.plan_evening_time)
        ):
            await self._send_evening_digest(now)
            self._evening_sent_date = today

    def _is_digest_time(self, now: datetime, time_str: str) -> bool:
        """Проверить совпадение текущего времени с настройкой дайджеста."""
        if not time_str or not re.match(r"^\d{2}:\d{2}$", time_str):
            return False
        parts = time_str.split(":")
        hour, minute = int(parts[0]), int(parts[1])
        scheduled = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        diff = abs((now - scheduled).total_seconds())
        return diff <= _DIGEST_TOLERANCE

    async def _send_morning_digest(self, now: datetime) -> None:
        """Отправить утренний дайджест всем admin-пользователям."""
        admin_uids = self._admin_uids()
        if not admin_uids:
            return

        today = now.date()

        for uid in admin_uids:
            try:
                projects_dir = get_user_projects_dir(self.settings, uid)
            except ValueError:
                continue

            # Собрать задачи из всех проектов
            all_items: list[PlanItem] = []
            carried: list[PlanItem] = []

            for project_path in self._get_all_project_dirs(uid, projects_dir):
                try:
                    items = ps.get_by_date(project_path, today)
                    all_items.extend(items)
                    carried.extend(i for i in items if i.carried_over)
                except InfrastructureError:
                    continue

            text = format_morning_digest(all_items, carried)
            await self._send(uid, text)

        log.info("Утренний дайджест отправлен %d admin", len(admin_uids))

    async def _send_evening_digest(self, now: datetime) -> None:
        """Отправить вечерний дайджест всем admin-пользователям."""
        admin_uids = self._admin_uids()
        if not admin_uids:
            return

        today = now.date()

        for uid in admin_uids:
            try:
                projects_dir = get_user_projects_dir(self.settings, uid)
            except ValueError:
                continue

            all_items: list[PlanItem] = []
            for project_path in self._get_all_project_dirs(uid, projects_dir):
                try:
                    items = ps.get_by_date(project_path, today)
                    all_items.extend(items)
                except InfrastructureError:
                    continue

            text = format_evening_summary(all_items)
            await self._send(uid, text)

        log.info("Вечерний дайджест отправлен %d admin", len(admin_uids))

    def _admin_uids(self) -> list[int]:
        """Список uid с ролью admin."""
        return [
            int(uid_str)
            for uid_str, cfg in self.settings.users.items()
            if cfg.get("role") == "admin"
        ]

    # ── Отправка ──

    async def _send(self, uid: int, text: str) -> None:
        """Отправить сообщение пользователю в Telegram."""
        try:
            await self.bot.send_message(uid, text, parse_mode="HTML")
        except TelegramForbiddenError:
            log.warning("Бот заблокирован пользователем uid=%d", uid)
        except Exception:
            log.error("Ошибка отправки uid=%d", uid, exc_info=True)


def _format_reminder(item: PlanItem, minutes_before: int) -> str:
    """Сформировать HTML-текст напоминания для Telegram."""
    emoji = CATEGORY_EMOJI.get(item.category, EMOJI_REMINDER)
    title = html_lib.escape(item.title)
    lines = [f"{emoji} <b>{title}</b>"]

    if minutes_before > 0:
        if minutes_before >= 1440:
            days = minutes_before // 1440
            lines.append(f"⏰ Через {days} д.")
        elif minutes_before >= 60:
            hours = minutes_before // 60
            lines.append(f"⏰ Через {hours} ч.")
        else:
            lines.append(f"⏰ Через {minutes_before} мин.")

    if item.description:
        lines.append(f"\n{html_lib.escape(item.description)}")

    return "\n".join(lines)
