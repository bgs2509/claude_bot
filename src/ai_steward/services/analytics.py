"""EventLogger — аналитика событий в SQLite."""

import asyncio
import logging
from datetime import datetime, timedelta, timezone

import aiosqlite

from ai_steward.config import Settings

log = logging.getLogger("ai-steward.analytics")

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id      TEXT NOT NULL,
    user_id         INTEGER,
    event_type      TEXT NOT NULL,
    input_summary   TEXT DEFAULT '',
    output_summary  TEXT DEFAULT '',
    duration_ms     INTEGER DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'ok',
    timestamp       TEXT NOT NULL
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events (timestamp)",
    "CREATE INDEX IF NOT EXISTS idx_events_user_id ON events (user_id)",
]


class EventLogger:
    """Запись событий бота в SQLite для аналитики."""

    def __init__(self, settings: Settings) -> None:
        self._db_path = settings.analytics_db
        self._retention_days = settings.analytics_retention_days
        self._db: aiosqlite.Connection | None = None
        self._cleanup_task: asyncio.Task | None = None

    async def init(self) -> None:
        """Открыть соединение, создать таблицу, запустить очистку."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(str(self._db_path))
        await self._db.execute("PRAGMA journal_mode=WAL")
        await self._db.execute(_CREATE_TABLE)
        for idx_sql in _CREATE_INDEXES:
            await self._db.execute(idx_sql)
        await self._db.commit()
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        log.info("EventLogger: %s", self._db_path)

    async def log_event(
        self,
        *,
        request_id: str,
        user_id: int | None,
        event_type: str,
        input_summary: str = "",
        output_summary: str = "",
        duration_ms: int = 0,
        status: str = "ok",
    ) -> None:
        """Записать событие. Ошибки логируются, не пробрасываются."""
        if not self._db:
            return
        try:
            await self._db.execute(
                "INSERT INTO events "
                "(request_id, user_id, event_type, input_summary, output_summary, "
                "duration_ms, status, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    request_id,
                    user_id,
                    event_type,
                    input_summary[:200],
                    output_summary[:200],
                    duration_ms,
                    status,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                ),
            )
            await self._db.commit()
        except Exception:
            log.warning("EventLogger: ошибка записи", exc_info=True)

    async def cleanup_old(self) -> None:
        """Удалить записи старше retention_days."""
        if not self._db:
            return
        cutoff = (
            datetime.now(timezone.utc) - timedelta(days=self._retention_days)
        ).isoformat(timespec="seconds")
        try:
            cursor = await self._db.execute(
                "DELETE FROM events WHERE timestamp < ?", (cutoff,)
            )
            await self._db.commit()
            if cursor.rowcount:
                log.info("EventLogger: удалено %d старых записей", cursor.rowcount)
        except Exception:
            log.warning("EventLogger: ошибка очистки", exc_info=True)

    async def close(self) -> None:
        """Закрыть соединение."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
        if self._db:
            await self._db.close()
            self._db = None

    async def _cleanup_loop(self) -> None:
        """Суточная очистка старых записей."""
        while True:
            await asyncio.sleep(86400)
            await self.cleanup_old()
