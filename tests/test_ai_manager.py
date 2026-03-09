"""Тесты менеджера AI-провайдеров."""

import unittest

from claude_bot.config import Settings
from claude_bot.services.ai.base import AIResponse
from claude_bot.services.ai.manager import AIManager
from claude_bot.state import AppState


class DummyProvider:
    """Простой тестовый провайдер."""

    def __init__(
        self,
        name: str,
        default_model: str,
        supports_sessions: bool,
        default_reasoning: str | None = None,
    ) -> None:
        self.name = name
        self._default_model = default_model
        self._supports_sessions = supports_sessions
        self._default_reasoning = default_reasoning
        self.last_request = None

    def list_models(self, settings: Settings) -> dict[str, str]:
        return {
            self._default_model: self._default_model,
            f"{self._default_model}-alt": f"{self._default_model}-alt",
        }

    def default_model(self, settings: Settings) -> str:
        return self._default_model

    def list_reasoning_levels(self, settings: Settings) -> dict[str, str]:
        if self._default_reasoning is None:
            return {}
        return {
            "low": "Low",
            "medium": "Medium",
            "high": "High",
            "xhigh": "Extra High",
        }

    def default_reasoning_effort(self, settings: Settings) -> str | None:
        return self._default_reasoning

    def supports_sessions(self) -> bool:
        return self._supports_sessions

    async def run(self, request, settings: Settings, state: AppState) -> AIResponse:
        self.last_request = request
        session_id = "session-123" if self._supports_sessions else None
        return AIResponse(text=f"{self.name}:{request.prompt}", session_id=session_id)


class AIManagerTests(unittest.IsolatedAsyncioTestCase):
    """Покрытие ключевой логики выбора провайдера."""

    def setUp(self) -> None:
        self.settings = Settings(
            telegram_bot_token="token",
            default_provider="claude",
            enabled_providers=["claude", "codex"],
            codex_models=["gpt-5-codex", "o3"],
        )
        self.state = AppState()
        self.manager = AIManager()
        self.manager.providers = {
            "claude": DummyProvider("claude", "sonnet", True),
            "codex": DummyProvider("codex", "gpt-5-codex", True, "xhigh"),
        }

    def test_default_provider_falls_back_to_first_enabled(self) -> None:
        settings = Settings(
            telegram_bot_token="token",
            default_provider="missing",
            enabled_providers=["codex", "claude"],
        )

        self.assertEqual(self.manager.default_provider_name(settings), "codex")

    def test_set_provider_resets_model_and_session(self) -> None:
        profile = self.state.get_or_create_user_ai(1, "claude")
        profile.model = "opus"
        profile.session_id = "abc"

        self.manager.set_provider(1, "codex", self.settings, self.state)

        self.assertEqual(profile.provider, "codex")
        self.assertIsNone(profile.model)
        self.assertIsNone(profile.reasoning_effort)
        self.assertIsNone(profile.session_id)

    def test_set_model_validates_against_current_provider(self) -> None:
        self.manager.set_provider(1, "codex", self.settings, self.state)
        self.manager.set_model(1, "gpt-5-codex-alt", self.settings, self.state)

        profile = self.manager.get_user_profile(1, self.settings, self.state)
        self.assertEqual(profile.model, "gpt-5-codex-alt")

        with self.assertRaises(ValueError):
            self.manager.set_model(1, "sonnet", self.settings, self.state)

    def test_set_reasoning_validates_against_current_provider(self) -> None:
        self.manager.set_provider(1, "codex", self.settings, self.state)
        self.manager.set_reasoning(1, "extra-high", self.settings, self.state)

        profile = self.manager.get_user_profile(1, self.settings, self.state)
        self.assertEqual(profile.reasoning_effort, "xhigh")

        self.manager.set_provider(2, "claude", self.settings, self.state)
        with self.assertRaises(ValueError):
            self.manager.set_reasoning(2, "high", self.settings, self.state)

    async def test_run_persists_session_for_stateful_provider(self) -> None:
        response = await self.manager.run("hello", 1, "admin", self.settings, self.state)

        profile = self.manager.get_user_profile(1, self.settings, self.state)
        self.assertEqual(response.text, "claude:hello")
        self.assertEqual(profile.session_id, "session-123")

    async def test_run_persists_session_for_codex_provider(self) -> None:
        self.manager.set_provider(1, "codex", self.settings, self.state)
        profile = self.manager.get_user_profile(1, self.settings, self.state)
        profile.session_id = "old-session"

        response = await self.manager.run("hello", 1, "readonly", self.settings, self.state)

        self.assertEqual(response.text, "codex:hello")
        self.assertEqual(profile.session_id, "session-123")
        self.assertEqual(self.manager.providers["codex"].last_request.reasoning_effort, "xhigh")


if __name__ == "__main__":
    unittest.main()
