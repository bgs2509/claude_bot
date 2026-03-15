"""Персистентное хранилище сессий и проектов."""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger("claude-bot.storage")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SessionInfo:
    id: str
    name: str
    created_at: str = ""
    last_used: str = ""

    def __post_init__(self) -> None:
        now = _now_iso()
        if not self.created_at:
            self.created_at = now
        if not self.last_used:
            self.last_used = now


@dataclass
class ProjectData:
    active_session: str | None = None
    sessions: list[SessionInfo] = field(default_factory=list)


@dataclass
class UserData:
    active_project: str | None = None
    projects: dict[str, ProjectData] = field(default_factory=dict)


class SessionStorage:
    """CRUD-хранилище сессий в JSON-файле. Проекты — из ФС."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = asyncio.Lock()
        self._data: dict[int, UserData] = {}
        self._load()

    # ── загрузка / сохранение ──

    def _load(self) -> None:
        if not self._path.exists():
            return
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
            for uid_str, udata in raw.items():
                uid = int(uid_str)
                projects = {}
                for pname, pdata in udata.get("projects", {}).items():
                    sessions = [SessionInfo(**s) for s in pdata.get("sessions", [])]
                    projects[pname] = ProjectData(
                        active_session=pdata.get("active_session"),
                        sessions=sessions,
                    )
                self._data[uid] = UserData(
                    active_project=udata.get("active_project"),
                    projects=projects,
                )
        except Exception as e:
            log.error("storage: ошибка загрузки %s: %s", self._path, e)

    async def _save(self) -> None:
        out: dict[str, dict] = {}
        for uid, udata in self._data.items():
            projects = {}
            for pname, pdata in udata.projects.items():
                projects[pname] = {
                    "active_session": pdata.active_session,
                    "sessions": [asdict(s) for s in pdata.sessions],
                }
            out[str(uid)] = {
                "active_project": udata.active_project,
                "projects": projects,
            }
        async with self._lock:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(
                json.dumps(out, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

    # ── пользователь ──

    def get_user(self, uid: int) -> UserData:
        if uid not in self._data:
            self._data[uid] = UserData()
        return self._data[uid]

    # ── проекты (из ФС) ──

    def list_projects(self, projects_dir: Path, limit: int | None = None) -> list[str]:
        """Список папок в projects_dir, отсортированных по mtime (новые первые)."""
        if not projects_dir.exists():
            return []
        dirs = [
            d for d in projects_dir.iterdir()
            if d.is_dir() and not d.name.startswith((".", "_"))
        ]
        dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
        names = [d.name for d in dirs]
        return names[:limit] if limit else names

    async def create_project(self, uid: int, name: str, projects_dir: Path) -> None:
        """mkdir + сделать активным."""
        (projects_dir / name).mkdir(parents=True, exist_ok=True)
        user = self.get_user(uid)
        if name not in user.projects:
            user.projects[name] = ProjectData()
        user.active_project = name
        await self._save()

    async def clear_active_project(self, uid: int) -> None:
        """Сбросить активный проект (работа в общей директории)."""
        user = self.get_user(uid)
        user.active_project = None
        await self._save()

    async def set_active_project(self, uid: int, name: str, projects_dir: Path) -> bool:
        """Переключить активный проект. Возвращает False если папки нет."""
        project_path = projects_dir / name
        if not project_path.is_dir():
            return False
        user = self.get_user(uid)
        user.active_project = name
        if name not in user.projects:
            user.projects[name] = ProjectData()
        await self._save()
        return True

    async def restore_last_session(self, uid: int) -> str | None:
        """Активировать последнюю использованную сессию текущего проекта.

        Returns:
            Имя восстановленной сессии или None если сессий нет.
        """
        pd = self._get_project_data(uid)
        if pd.active_session:
            for s in pd.sessions:
                if s.id == pd.active_session:
                    return s.name
            return None

        if not pd.sessions:
            return None

        last = max(pd.sessions, key=lambda s: s.last_used)
        pd.active_session = last.id
        await self._save()
        return last.name

    # ── сессии ──

    def _get_project_data(self, uid: int) -> ProjectData:
        """ProjectData для активного проекта (или дефолтного '__global__')."""
        user = self.get_user(uid)
        pname = user.active_project or "__global__"
        if pname not in user.projects:
            user.projects[pname] = ProjectData()
        return user.projects[pname]

    def get_active_session_id(self, uid: int) -> str | None:
        return self._get_project_data(uid).active_session

    async def save_session(
        self, uid: int, session_id: str, name: str | None = None,
    ) -> None:
        """Сохранить/обновить сессию и сделать активной."""
        pd = self._get_project_data(uid)
        now = _now_iso()
        for s in pd.sessions:
            if s.id == session_id:
                s.last_used = now
                if name:
                    s.name = name
                pd.active_session = session_id
                await self._save()
                return
        # Новая сессия
        sname = name or f"Session {len(pd.sessions) + 1}"
        pd.sessions.append(SessionInfo(id=session_id, name=sname))
        pd.active_session = session_id
        await self._save()

    async def update_session_name(
        self, uid: int, session_id: str, name: str,
    ) -> None:
        pd = self._get_project_data(uid)
        for s in pd.sessions:
            if s.id == session_id:
                s.name = name
                await self._save()
                return

    async def set_active_session(self, uid: int, session_id: str) -> bool:
        """Переключить активную сессию. Возвращает False если не найдена."""
        pd = self._get_project_data(uid)
        for s in pd.sessions:
            if s.id == session_id:
                s.last_used = _now_iso()
                pd.active_session = session_id
                await self._save()
                return True
        return False

    async def create_new_session(self, uid: int) -> None:
        """Сбросить active_session (следующее сообщение начнёт новую)."""
        pd = self._get_project_data(uid)
        pd.active_session = None
        await self._save()

    def get_recent_sessions(self, uid: int, limit: int = 3) -> list[SessionInfo]:
        """Последние N сессий (по last_used)."""
        pd = self._get_project_data(uid)
        sorted_sessions = sorted(
            pd.sessions, key=lambda s: s.last_used, reverse=True,
        )
        return sorted_sessions[:limit]

    def get_all_sessions(self, uid: int) -> list[SessionInfo]:
        """Все сессии активного проекта (по last_used)."""
        pd = self._get_project_data(uid)
        return sorted(pd.sessions, key=lambda s: s.last_used, reverse=True)
