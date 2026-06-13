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
            (base_dir / "runtime.example.yaml").write_text(
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


if __name__ == "__main__":
    unittest.main()
