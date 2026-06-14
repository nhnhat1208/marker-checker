from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from marker_checker_agent.config import load_runtime_config


class ConfigOverridesTest(unittest.TestCase):
    def test_runtime_env_overrides_deploy_settings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            (base_dir / "runtime.yaml").write_text(
                "\n".join(
                    [
                        "telegram:",
                        "  enabled: true",
                        "  polling_enabled: true",
                        "  bot_token: \"\"",
                        "google_sheets:",
                        "  enabled: true",
                        "  spreadsheet_id: \"\"",
                        "  service_account_json_base64: \"\"",
                        "ai:",
                        "  enabled: false",
                    ]
                ),
                encoding="utf-8",
            )

            with patch.dict(
                os.environ,
                {
                    "TELEGRAM_ENABLED": "true",
                    "TELEGRAM_POLLING_ENABLED": "false",
                    "TELEGRAM_BOT_TOKEN": "deploy-token",
                    "GOOGLE_SHEETS_ENABLED": "true",
                    "GOOGLE_SHEETS_SPREADSHEET_ID": "sheet-123",
                    "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64": "base64-creds",
                    "AI_ENABLED": "true",
                    "AI_PROMPT_VERSION": "request-parse-v2",
                    "AI_MODEL": "gpt-test",
                    "AI_BASE_URL": "https://example.test/v1",
                    "AI_API_KEY": "api-key-123",
                    "AI_TIMEOUT_SECONDS": "30",
                    "AI_MAX_TOKENS": "1200",
                    "AI_TEMPERATURE": "0.2",
                    "AI_TOP_P": "0.9",
                    "AI_PRESENCE_PENALTY": "0.1",
                },
                clear=False,
            ):
                config = load_runtime_config(base_dir)

        self.assertTrue(config.telegram.enabled)
        self.assertFalse(config.telegram.polling_enabled)
        self.assertEqual(config.telegram.bot_token, "deploy-token")
        self.assertTrue(config.google_sheets.enabled)
        self.assertEqual(config.google_sheets.spreadsheet_id, "sheet-123")
        self.assertEqual(
            config.google_sheets.service_account_json_base64,
            "base64-creds",
        )
        self.assertTrue(config.ai.enabled)
        self.assertEqual(config.ai.prompt_version, "request-parse-v2")
        self.assertEqual(config.ai.model, "gpt-test")
        self.assertEqual(config.ai.base_url, "https://example.test/v1")
        self.assertEqual(config.ai.api_key, "api-key-123")
        self.assertEqual(config.ai.timeout_seconds, 30.0)
        self.assertEqual(config.ai.max_tokens, 1200)
        self.assertEqual(config.ai.temperature, 0.2)
        self.assertEqual(config.ai.top_p, 0.9)
        self.assertEqual(config.ai.presence_penalty, 0.1)

    def test_missing_runtime_files_fail_fast(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir, self.assertRaises(FileNotFoundError):
            load_runtime_config(Path(temp_dir))

    def test_missing_required_values_raise_clear_error(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            base_dir = Path(temp_dir)
            (base_dir / "runtime.yaml").write_text(
                "\n".join(
                    [
                        "telegram:",
                        "  enabled: true",
                        "  bot_token: \"\"",
                        "google_sheets:",
                        "  enabled: true",
                        "  spreadsheet_id: \"\"",
                        "  service_account_file: \"\"",
                        "  service_account_json_base64: \"\"",
                        "ai:",
                        "  enabled: true",
                        "  model: \"\"",
                        "  base_url: \"\"",
                        "  api_key: \"\"",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as exc_info:
                load_runtime_config(base_dir)

        message = str(exc_info.exception)
        self.assertIn("telegram.bot_token is required", message)
        self.assertIn("google_sheets.spreadsheet_id is required", message)
        self.assertIn("Google Sheets credentials are required", message)
        self.assertIn("ai.model is required", message)


if __name__ == "__main__":
    unittest.main()
