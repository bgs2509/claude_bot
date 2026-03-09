"""Менеджер выбора AI-провайдера и пользовательского профиля."""

from claude_bot.config import Settings
from claude_bot.services.ai.base import AIRequest, AIResponse, AIProvider
from claude_bot.services.ai.providers.claude_cli import ClaudeCLIProvider
from claude_bot.services.ai.providers.codex_cli import CodexCLIProvider
from claude_bot.state import AppState, UserAIState


class AIManager:
    """Единая точка работы с AI-провайдерами."""

    def __init__(self) -> None:
        self.providers: dict[str, AIProvider] = {
            "claude": ClaudeCLIProvider(),
            "codex": CodexCLIProvider(),
        }

    def list_providers(self, settings: Settings) -> list[str]:
        return [name for name in settings.enabled_providers if name in self.providers]

    def default_provider_name(self, settings: Settings) -> str:
        providers = self.list_providers(settings)
        if settings.default_provider in providers:
            return settings.default_provider
        if providers:
            return providers[0]
        return "claude"

    def get_provider(self, provider_name: str) -> AIProvider:
        provider = self.providers.get(provider_name)
        if provider is None:
            raise ValueError(f"Неизвестный AI-провайдер: {provider_name}")
        return provider

    def _resolve_choice(self, value: str, choices: dict[str, str]) -> str | None:
        normalized = value.strip().lower()
        alias_map = {
            "extra high": "xhigh",
            "extra-high": "xhigh",
            "extra_high": "xhigh",
        }
        normalized = alias_map.get(normalized, normalized)

        for key in choices:
            if key.lower() == normalized:
                return key
        return None

    def get_user_profile(self, uid: int, settings: Settings, state: AppState) -> UserAIState:
        profile = state.get_or_create_user_ai(uid, self.default_provider_name(settings))
        if profile.provider not in self.list_providers(settings):
            profile.provider = self.default_provider_name(settings)
            profile.model = None
            profile.reasoning_effort = None
            profile.session_id = None
        return profile

    def get_current_provider_name(self, uid: int, settings: Settings, state: AppState) -> str:
        return self.get_user_profile(uid, settings, state).provider

    def get_current_provider(self, uid: int, settings: Settings, state: AppState) -> AIProvider:
        provider_name = self.get_current_provider_name(uid, settings, state)
        return self.get_provider(provider_name)

    def list_models(
        self,
        uid: int,
        settings: Settings,
        state: AppState,
        provider_name: str | None = None,
    ) -> dict[str, str]:
        provider = self.get_provider(provider_name or self.get_current_provider_name(uid, settings, state))
        return provider.list_models(settings)

    def get_current_model(self, uid: int, settings: Settings, state: AppState) -> str:
        profile = self.get_user_profile(uid, settings, state)
        provider = self.get_provider(profile.provider)
        return profile.model or provider.default_model(settings)

    def list_reasoning_levels(
        self,
        uid: int,
        settings: Settings,
        state: AppState,
        provider_name: str | None = None,
    ) -> dict[str, str]:
        provider = self.get_provider(provider_name or self.get_current_provider_name(uid, settings, state))
        return provider.list_reasoning_levels(settings)

    def get_current_reasoning(self, uid: int, settings: Settings, state: AppState) -> str | None:
        profile = self.get_user_profile(uid, settings, state)
        provider = self.get_provider(profile.provider)
        return profile.reasoning_effort or provider.default_reasoning_effort(settings)

    def set_provider(
        self,
        uid: int,
        provider_name: str,
        settings: Settings,
        state: AppState,
    ) -> None:
        if provider_name not in self.list_providers(settings):
            raise ValueError(
                f"Неизвестный провайдер. Доступные: {' | '.join(self.list_providers(settings))}"
            )

        profile = self.get_user_profile(uid, settings, state)
        if profile.provider == provider_name:
            return

        profile.provider = provider_name
        profile.model = None
        profile.reasoning_effort = None
        profile.session_id = None

    def set_model(self, uid: int, model_name: str, settings: Settings, state: AppState) -> None:
        profile = self.get_user_profile(uid, settings, state)
        models = self.list_models(uid, settings, state, profile.provider)
        resolved_model = self._resolve_choice(model_name, models)
        if resolved_model is None:
            raise ValueError(f"Неизвестная модель. Доступные: {' | '.join(models.keys())}")

        profile.model = resolved_model

    def set_reasoning(self, uid: int, reasoning: str, settings: Settings, state: AppState) -> None:
        profile = self.get_user_profile(uid, settings, state)
        levels = self.list_reasoning_levels(uid, settings, state, profile.provider)
        if not levels:
            raise ValueError("Текущий провайдер не поддерживает настройку reasoning.")

        resolved_reasoning = self._resolve_choice(reasoning, levels)
        if resolved_reasoning is None:
            raise ValueError(f"Неизвестный reasoning. Доступные: {' | '.join(levels.keys())}")

        profile.reasoning_effort = resolved_reasoning

    def reset_session(self, uid: int, settings: Settings, state: AppState) -> None:
        profile = self.get_user_profile(uid, settings, state)
        profile.session_id = None

    async def run(
        self,
        prompt: str,
        uid: int,
        role: str,
        settings: Settings,
        state: AppState,
    ) -> AIResponse:
        profile = self.get_user_profile(uid, settings, state)
        provider = self.get_provider(profile.provider)

        request = AIRequest(
            user_id=uid,
            prompt=prompt,
            role=role,
            model=profile.model or provider.default_model(settings),
            reasoning_effort=profile.reasoning_effort or provider.default_reasoning_effort(settings),
            session_id=profile.session_id,
            workdir=settings.projects_dir,
        )
        response = await provider.run(request, settings, state)

        if provider.supports_sessions():
            profile.session_id = response.session_id or profile.session_id
        else:
            profile.session_id = None

        return response
