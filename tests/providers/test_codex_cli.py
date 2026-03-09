"""Тесты адаптера Codex CLI."""

import unittest
from pathlib import Path

from claude_bot.config import Settings
from claude_bot.services.ai.base import AIRequest
from claude_bot.services.ai.providers.codex_cli import CodexCLIProvider


class CodexCLIProviderTests(unittest.TestCase):
    """Проверка resume-логики и парсинга JSONL событий."""

    def setUp(self) -> None:
        self.provider = CodexCLIProvider()
        self.settings = Settings(
            telegram_bot_token="token",
            codex_bin="codex",
            codex_default_model="gpt-5.4",
            codex_default_reasoning_effort="xhigh",
        )
        self.workdir = Path("/tmp/workdir")

    def test_build_command_for_new_exec_uses_read_only_sandbox(self) -> None:
        request = AIRequest(
            user_id=1,
            prompt="hello",
            role="readonly",
            model="gpt-5.4",
            reasoning_effort="high",
            session_id=None,
            workdir=self.workdir,
        )

        cmd = self.provider._build_command(request, self.settings, "/tmp/out.txt")

        self.assertEqual(cmd[:3], ["codex", "exec", "--skip-git-repo-check"])
        self.assertIn("-C", cmd)
        self.assertIn('-c', cmd)
        self.assertIn('model_reasoning_effort="high"', cmd)
        self.assertIn("--sandbox", cmd)
        self.assertIn("read-only", cmd)

    def test_build_command_for_resume_uses_resume_subcommand(self) -> None:
        request = AIRequest(
            user_id=1,
            prompt="continue",
            role="admin",
            model="gpt-5.4",
            reasoning_effort="xhigh",
            session_id="019cca52-531a-7761-889d-5c34a782cd18",
            workdir=self.workdir,
        )

        cmd = self.provider._build_command(request, self.settings, "/tmp/out.txt")

        self.assertEqual(cmd[:4], ["codex", "exec", "resume", "--skip-git-repo-check"])
        self.assertIn("--dangerously-bypass-approvals-and-sandbox", cmd)
        self.assertIn('model_reasoning_effort="xhigh"', cmd)
        self.assertIn("019cca52-531a-7761-889d-5c34a782cd18", cmd)
        self.assertNotIn("-C", cmd)
        self.assertNotIn("--sandbox", cmd)

    def test_extract_thread_id_from_jsonl(self) -> None:
        stdout = b"""
warning line
{"type":"thread.started","thread_id":"019cca52-531a-7761-889d-5c34a782cd18"}
{"type":"turn.started"}
"""

        thread_id = self.provider._extract_thread_id(stdout)

        self.assertEqual(thread_id, "019cca52-531a-7761-889d-5c34a782cd18")

    def test_sanitize_stderr_removes_codex_internal_noise(self) -> None:
        stderr = b"""
WARNING: proceeding, even though we could not update PATH: Operation not permitted (os error 1)
2026-03-07T22:22:24.586974Z ERROR codex_core::codex: failed to load skill /Users/yfedorov/.codex/skills/go-expert-developer/SKILL.md: invalid description: exceeds maximum length of 1024 characters
thread 'main' panicked at something
ChatGPT account ID not available, please re-run `codex login`
"""

        text = self.provider._sanitize_stderr(stderr)

        self.assertEqual(text, "ChatGPT account ID not available, please re-run `codex login`")

    def test_fallback_text_returns_generic_message_for_internal_only_logs(self) -> None:
        stderr = b"""
2026-03-07T22:22:24.586974Z ERROR codex_core::codex: failed to load skill /Users/yfedorov/.codex/skills/go-expert-developer/SKILL.md: invalid description: exceeds maximum length of 1024 characters
"""

        text = self.provider._fallback_text(stderr, b'{"type":"thread.started"}\n', 0)

        self.assertEqual(text, "Codex не вернул итоговый ответ.")


if __name__ == "__main__":
    unittest.main()
