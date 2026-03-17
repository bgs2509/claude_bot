"""Менеджер уведомлений: фоновый цикл проверки и отправки в Telegram."""

from __future__ import annotations

import asyncio
import html as html_lib
import logging
import zoneinfo
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

from aiogram.exceptions import TelegramForbiddenError

from claude_bot.config import Settings, get_user_projects_dir
from claude_bot.constants import CATEGORY_EMOJI, EMOJI_REMINDER
from claude_bot.errors import InfrastructureError
from claude_bot.models.notification import Notification
from claude_bot.services import notification_service as ns

if TYPE_CHECKING:
    from aiogram import Bot
    from claude_bot.services.storage import SessionStorage

log = logging.getLogger("claude-bot.notification-manager")


class NotificationManager:
    """Фоновый сервис проверки и отправки уведомлений."""

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

    async def init(self) -> None:
        """Запустить фоновый цикл сканирования."""
        self._task = asyncio.create_task(self._scan_loop())
        log.info(
            "NotificationManager запущен, интервал=%ds",
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
        log.info("NotificationManager остановлен")

    async def _scan_loop(self) -> None:
        """Бесконечный цикл: проверка всех notify.json."""
        # Первый цикл — baseline (не отправлять, только запомнить)
        try:
            await self._scan_all(dry_run=True)
        except Exception:
            log.warning(
                "Ошибка первичного сканирования — работаем без baseline, "
                "возможны дубли при первом цикле",
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

        for uid_str, cfg in self.settings.users.items():
            uid = int(uid_str)
            try:
                projects_dir = get_user_projects_dir(self.settings, uid)
            except ValueError:
                continue

            # Собрать все директории проектов (включая __global__)
            project_dirs = self._get_all_project_dirs(uid, projects_dir)

            for project_path in project_dirs:
                try:
                    sent = await self._check_project(
                        uid, project_path, now, dry_run=dry_run,
                        projects_dir=projects_dir,
                    )
                    total_sent += sent
                except InfrastructureError as e:
                    log.warning(
                        "Ошибка notify.json: uid=%d path=%s: %s",
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

        # __global__
        global_dir = projects_dir / "__global__"
        if global_dir.is_dir():
            dirs.append(global_dir)

        # Обычные проекты
        project_names = self.storage.list_projects(projects_dir)
        for name in project_names:
            dirs.append(projects_dir / name)

        return dirs

    async def _check_project(
        self,
        uid: int,
        project_path: Path,
        now: datetime,
        *,
        dry_run: bool = False,
        projects_dir: Path | None = None,
    ) -> int:
        """Проверить один проект, отправить все due-уведомления.

        Returns:
            Количество отправленных уведомлений.
        """
        notify_path = project_path / ns.FILENAME
        if not notify_path.exists():
            return 0

        notifications = ns.get_active(project_path)
        if not notifications:
            return 0

        sent_count = 0
        for notification in notifications:
            due_minutes = ns.is_due(notification, now)
            if not due_minutes:
                continue

            if dry_run:
                # Первый запуск — пометить как отправленные без реальной отправки
                ns.mark_sent(project_path, notification, due_minutes)
                continue

            # Вычислить тег проекта
            proj_name = project_path.name if project_path.name != "__global__" else "Общий"
            tag = f"<code>[{proj_name}]</code>\n\n"

            # Отправить каждому авторизованному получателю
            for minutes in due_minutes:
                text = _format_notification(notification, minutes)
                for recipient in notification.recipients:
                    if str(recipient) not in self.settings.users:
                        log.warning(
                            "notify: recipient uid=%d не в allowlist",
                            recipient,
                        )
                        continue
                    await self._send(recipient, tag + text)

            ns.mark_sent(project_path, notification, due_minutes)
            sent_count += 1

        return sent_count

    async def _send(self, uid: int, text: str) -> None:
        """Отправить уведомление пользователю в Telegram."""
        try:
            await self.bot.send_message(uid, text, parse_mode="HTML")
        except TelegramForbiddenError:
            log.warning("Бот заблокирован пользователем uid=%d", uid)
        except Exception:
            log.error("Ошибка отправки uid=%d", uid, exc_info=True)


def _format_notification(notification: Notification, minutes_before: int) -> str:
    """Сформировать HTML-текст уведомления для Telegram."""
    emoji = CATEGORY_EMOJI.get(notification.category, EMOJI_REMINDER)
    title = html_lib.escape(notification.title)
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

    if notification.description:
        lines.append(f"\n{html_lib.escape(notification.description)}")

    return "\n".join(lines)
