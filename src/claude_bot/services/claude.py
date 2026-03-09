"""Совместимость со старым Claude API поверх нового provider-слоя."""

from claude_bot.config import Settings
from claude_bot.services.ai.base import AIRequest, AIResponse
from claude_bot.services.ai.providers.claude_cli import CLAUDE_MODELS as MODELS
from claude_bot.services.ai.providers.claude_cli import ClaudeCLIProvider
from claude_bot.services.telegram_output import send_long
from claude_bot.state import AppState

ClaudeResponse = AIResponse


async def run_claude(
    prompt: str,
    uid: int,
    settings: Settings,
    state: AppState,
) -> ClaudeResponse:
    """Запустить Claude через новый provider-layer."""

    provider = ClaudeCLIProvider()
    profile = state.get_or_create_user_ai(uid, settings.default_provider)
    request = AIRequest(
        user_id=uid,
        prompt=prompt,
        role="readonly",
        model=profile.model or provider.default_model(settings),
        reasoning_effort=None,
        session_id=profile.session_id,
        workdir=settings.projects_dir,
    )

    cfg = settings.users.get(str(uid))
    if cfg:
        request.role = cfg.get("role", "readonly")

    response = await provider.run(request, settings, state)
    profile.provider = "claude"
    profile.reasoning_effort = None
    profile.session_id = response.session_id
    return response
