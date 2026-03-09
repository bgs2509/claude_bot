"""Общие типы и константы для AI-провайдеров."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from claude_bot.config import Settings
    from claude_bot.state import AppState


BOT_SYSTEM_PROMPT = (
    "ФОРМАТ ОТВЕТА: "
    "НИКОГДА не используй таблицы. "
    "Вместо таблиц используй маркированные или нумерованные списки. "
    "Форматирование: plain text, списки, переносы строк. "
    "Файлы сохраняй в _output/. "
    "Пользователь общается через Telegram-бот. "
    "Он может просить выполнить bash-команды (cd, ls, mkdir, git и любые другие) — выполняй их. "
    "При смене директории сообщай текущий путь. "
    "Долгие процессы (серверы, make dev, npm start, yarn dev и т.п.) запускай в фоне: "
    "nohup <команда> &> /tmp/bot_proc.log & disown. Сообщай PID и путь к логу."
)


@dataclass(slots=True)
class AIRequest:
    """Нормализованный запрос к AI-провайдеру."""

    user_id: int
    prompt: str
    role: str
    model: str | None
    reasoning_effort: str | None
    session_id: str | None
    workdir: Path


@dataclass(slots=True)
class AIResponse:
    """Нормализованный ответ от AI-провайдера."""

    text: str
    session_id: str | None = None
    files: list[Path] = field(default_factory=list)


class AIProvider(Protocol):
    """Контракт для CLI/API провайдеров."""

    name: str

    def list_models(self, settings: "Settings") -> dict[str, str]:
        """Список доступных коротких имён моделей и их реальных идентификаторов."""

    def default_model(self, settings: "Settings") -> str:
        """Короткое имя модели по умолчанию."""

    def list_reasoning_levels(self, settings: "Settings") -> dict[str, str]:
        """Список уровней reasoning, если провайдер поддерживает их выбор."""

    def default_reasoning_effort(self, settings: "Settings") -> str | None:
        """Уровень reasoning по умолчанию или None, если он не поддерживается."""

    def supports_sessions(self) -> bool:
        """Поддерживает ли провайдер возобновление сессий."""

    async def run(
        self,
        request: AIRequest,
        settings: "Settings",
        state: "AppState",
    ) -> AIResponse:
        """Выполнить запрос и вернуть ответ провайдера."""
