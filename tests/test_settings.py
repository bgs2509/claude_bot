"""Тесты парсинга конфигурации."""

import tempfile
import unittest
from pathlib import Path

from claude_bot.config import Settings


class SettingsTests(unittest.TestCase):
    """Проверка новых env-полей multi-provider конфигурации."""

    def test_parse_csv_lists(self) -> None:
        settings = Settings(
            telegram_bot_token="token",
            enabled_providers="claude, codex",
            codex_models="gpt-5-codex, o3",
            codex_reasoning_levels="low, medium, xhigh",
        )

        self.assertEqual(settings.enabled_providers, ["claude", "codex"])
        self.assertEqual(settings.codex_models, ["gpt-5-codex", "o3"])
        self.assertEqual(settings.codex_reasoning_levels, ["low", "medium", "xhigh"])

    def test_parse_csv_lists_from_dotenv_source(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            env_path.write_text(
                "\n".join(
                    [
                        "TELEGRAM_BOT_TOKEN=token",
                        "ENABLED_PROVIDERS=claude,codex",
                        "CODEX_MODELS=gpt-5.4,gpt-5.3-codex",
                        "CODEX_REASONING_LEVELS=low,medium,xhigh",
                        'USERS={"1":{"role":"admin","limit":0,"name":"Admin"}}',
                    ]
                ),
                encoding="utf-8",
            )

            settings = Settings(_env_file=env_path)

            self.assertEqual(settings.enabled_providers, ["claude", "codex"])
            self.assertEqual(settings.codex_models, ["gpt-5.4", "gpt-5.3-codex"])
            self.assertEqual(settings.codex_reasoning_levels, ["low", "medium", "xhigh"])
            self.assertEqual(settings.users["1"]["role"], "admin")


if __name__ == "__main__":
    unittest.main()
