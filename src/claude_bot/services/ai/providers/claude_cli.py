"""Провайдер Claude Code CLI."""

import asyncio
import json
import logging
import os

from claude_bot.config import Settings
from claude_bot.services.ai.base import AIRequest, AIResponse, AIProvider, BOT_SYSTEM_PROMPT
from claude_bot.services.ai.files import collect_output_files, prepare_output_dir
from claude_bot.state import AppState

log = logging.getLogger("claude-bot")

CLAUDE_MODELS: dict[str, str] = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}


class ClaudeCLIProvider(AIProvider):
    """Адаптер текущего Claude Code CLI."""

    name = "claude"

    def list_models(self, settings: Settings) -> dict[str, str]:
        return CLAUDE_MODELS

    def default_model(self, settings: Settings) -> str:
        return "sonnet"

    def list_reasoning_levels(self, settings: Settings) -> dict[str, str]:
        return {}

    def default_reasoning_effort(self, settings: Settings) -> str | None:
        return None

    def supports_sessions(self) -> bool:
        return True

    async def run(
        self,
        request: AIRequest,
        settings: Settings,
        state: AppState,
    ) -> AIResponse:
        cwd = request.workdir
        media_before = prepare_output_dir(cwd)

        model_name = request.model or self.default_model(settings)
        model_id = self.list_models(settings).get(model_name, CLAUDE_MODELS["sonnet"])

        cmd = [
            settings.claude_bin,
            "-p",
            request.prompt,
            "--output-format",
            "json",
            "--append-system-prompt",
            BOT_SYSTEM_PROMPT,
            "--model",
            model_id,
        ]

        if request.session_id:
            log.info("[uid=%s] resuming Claude session %s", request.user_id, request.session_id)
            cmd += ["--resume", request.session_id]
        else:
            log.info("[uid=%s] starting new Claude session", request.user_id)

        if request.role in ("admin", "user"):
            cmd += ["--dangerously-skip-permissions"]

        env = os.environ.copy()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(cwd),
            env=env,
        )
        state.active_processes[request.user_id] = proc

        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=settings.claude_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return AIResponse(
                text=(
                    f"⏰ Таймаут ({settings.claude_timeout // 60} мин). "
                    "Используй /cancel для прерывания."
                )
            )
        finally:
            state.active_processes.pop(request.user_id, None)

        raw = stdout.decode().strip()
        if not raw:
            err = stderr.decode().strip()
            return AIResponse(text=err if err else "(пустой ответ)")

        result_text = raw
        session_id = None
        try:
            data = json.loads(raw)
            result_text = data.get("result", raw)
            session_id = data.get("session_id")
        except json.JSONDecodeError:
            pass

        files = collect_output_files(cwd, media_before)
        return AIResponse(text=result_text, session_id=session_id, files=files)
