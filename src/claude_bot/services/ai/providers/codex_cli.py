"""Провайдер Codex CLI."""

import asyncio
import json
import logging
import os
import re
import tempfile

from claude_bot.config import Settings
from claude_bot.services.ai.base import AIRequest, AIResponse, AIProvider, BOT_SYSTEM_PROMPT
from claude_bot.services.ai.files import collect_output_files, prepare_output_dir
from claude_bot.state import AppState

log = logging.getLogger("claude-bot")

REASONING_LABELS = {
    "low": "Low",
    "medium": "Medium",
    "high": "High",
    "xhigh": "Extra High",
}


class CodexCLIProvider(AIProvider):
    """Адаптер Codex CLI."""

    name = "codex"

    def list_models(self, settings: Settings) -> dict[str, str]:
        return {model: model for model in settings.codex_models}

    def default_model(self, settings: Settings) -> str:
        return settings.codex_default_model

    def list_reasoning_levels(self, settings: Settings) -> dict[str, str]:
        return {
            level: REASONING_LABELS.get(level, level)
            for level in settings.codex_reasoning_levels
        }

    def default_reasoning_effort(self, settings: Settings) -> str | None:
        return settings.codex_default_reasoning_effort

    def supports_sessions(self) -> bool:
        return True

    def _build_command(self, request: AIRequest, settings: Settings, output_path: str) -> list[str]:
        """Собрать команду Codex CLI для нового или возобновлённого треда."""

        model_name = request.model or self.default_model(settings)
        reasoning_effort = request.reasoning_effort or self.default_reasoning_effort(settings)
        prompt = (
            f"{BOT_SYSTEM_PROMPT}\n\n"
            f"Задача пользователя:\n{request.prompt}"
        )

        if request.session_id:
            cmd = [
                settings.codex_bin,
                "exec",
                "resume",
                "--skip-git-repo-check",
                "--json",
                "--output-last-message",
                output_path,
                "--model",
                model_name,
            ]
            if reasoning_effort:
                cmd += ["-c", f'model_reasoning_effort="{reasoning_effort}"']
            if request.role in ("admin", "user"):
                cmd.append("--dangerously-bypass-approvals-and-sandbox")
            cmd += [request.session_id, prompt]
            return cmd

        cmd = [
            settings.codex_bin,
            "exec",
            "--skip-git-repo-check",
            "--json",
            "--output-last-message",
            output_path,
            "-C",
            str(request.workdir),
            "--model",
            model_name,
        ]
        if reasoning_effort:
            cmd += ["-c", f'model_reasoning_effort="{reasoning_effort}"']

        if request.role in ("admin", "user"):
            cmd.append("--dangerously-bypass-approvals-and-sandbox")
        else:
            cmd += ["--sandbox", "read-only"]

        cmd.append(prompt)
        return cmd

    def _extract_thread_id(self, stdout: bytes) -> str | None:
        """Извлечь thread_id из JSONL stdout Codex CLI."""

        for line in stdout.decode(errors="replace").splitlines():
            payload = line.strip()
            if not payload.startswith("{"):
                continue
            try:
                data = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if data.get("type") == "thread.started":
                thread_id = data.get("thread_id")
                if isinstance(thread_id, str) and thread_id:
                    return thread_id
        return None

    def _sanitize_stderr(self, stderr: bytes) -> str:
        """Оставить только пользовательски полезные строки stderr."""

        filtered_lines: list[str] = []
        timestamped_log = re.compile(r"^\d{4}-\d{2}-\d{2}T.*\s(?:WARN|ERROR)\s")
        ignored_prefixes = (
            "thread '",
            "note: run with ",
            "Caused by:",
            "WARNING: proceeding, even though we could not update PATH:",
        )
        ignored_exact = {
            "Attempted to create a NULL object.",
            "event loop thread panicked",
            "inner future panicked during poll",
            "Could not create otel exporter: panicked during initialization",
        }

        for raw_line in stderr.decode(errors="replace").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if timestamped_log.match(line):
                continue
            if any(line.startswith(prefix) for prefix in ignored_prefixes):
                continue
            if line in ignored_exact:
                continue
            filtered_lines.append(line)

        return "\n".join(filtered_lines)

    def _fallback_text(self, stderr: bytes, stdout: bytes, returncode: int | None) -> str:
        """Сформировать безопасный fallback, если Codex не записал итоговый ответ."""

        sanitized_stderr = self._sanitize_stderr(stderr)
        if sanitized_stderr:
            return sanitized_stderr

        stdout_lines = [
            line.strip()
            for line in stdout.decode(errors="replace").splitlines()
            if line.strip() and not line.strip().startswith("{")
        ]
        if stdout_lines:
            return "\n".join(stdout_lines[:10])

        if returncode and returncode != 0:
            return f"Codex завершился с ошибкой (exit code {returncode}) и не вернул итоговый ответ."

        return "Codex не вернул итоговый ответ."

    async def run(
        self,
        request: AIRequest,
        settings: Settings,
        state: AppState,
    ) -> AIResponse:
        cwd = request.workdir
        media_before = prepare_output_dir(cwd)

        fd, output_path = tempfile.mkstemp(suffix=".txt")
        os.close(fd)
        cmd = self._build_command(request, settings, output_path)

        log.info(
            "[uid=%s] running Codex model=%s resume=%s",
            request.user_id,
            request.model or self.default_model(settings),
            bool(request.session_id),
        )
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
                timeout=settings.codex_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            return AIResponse(
                text=(
                    f"⏰ Таймаут ({settings.codex_timeout // 60} мин). "
                    "Используй /cancel для прерывания."
                ),
                session_id=request.session_id,
            )
        finally:
            state.active_processes.pop(request.user_id, None)

        thread_id = self._extract_thread_id(stdout)
        text = ""
        try:
            with open(output_path, encoding="utf-8") as output_file:
                text = output_file.read().strip()
        finally:
            try:
                os.unlink(output_path)
            except OSError:
                pass

        if not text:
            text = self._fallback_text(stderr, stdout, proc.returncode)

        files = collect_output_files(cwd, media_before)
        return AIResponse(
            text=text,
            session_id=thread_id or request.session_id,
            files=files,
        )
