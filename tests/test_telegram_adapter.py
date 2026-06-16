from __future__ import annotations

import asyncio
import threading
import unittest
from unittest.mock import patch

from agent.adapters.telegram_adapter import TelegramAdapter
from agent.config import TelegramConfig


class DummyOrchestrator:
    pass


class FakeApplication:
    def __init__(self) -> None:
        self.kwargs: dict | None = None
        self.loop_available = False
        self.loop_error: Exception | None = None

    def run_polling(self, **kwargs) -> None:
        self.kwargs = kwargs
        try:
            asyncio.get_event_loop()
        except Exception as exc:  # pragma: no cover - regression capture
            self.loop_error = exc
            return
        self.loop_available = True


class TelegramAdapterTest(unittest.TestCase):
    def test_run_polling_creates_event_loop_for_background_thread(self) -> None:
        adapter = TelegramAdapter(
            config=TelegramConfig(enabled=True, mode="polling", bot_token="token"),
            orchestrator=DummyOrchestrator(),  # type: ignore[arg-type]
        )
        fake_application = FakeApplication()
        adapter._application = fake_application  # type: ignore[assignment]

        polling_thread = threading.Thread(target=adapter._run_polling)
        polling_thread.start()
        polling_thread.join(timeout=5)

        self.assertFalse(polling_thread.is_alive())
        self.assertIsNone(fake_application.loop_error)
        self.assertTrue(fake_application.loop_available)
        self.assertEqual(
            fake_application.kwargs,
            {
                "drop_pending_updates": True,
                "close_loop": False,
                "stop_signals": None,
            },
        )

    def test_start_polling_skips_blank_token(self) -> None:
        adapter = TelegramAdapter(
            config=TelegramConfig(enabled=True, mode="polling", bot_token="   "),
            orchestrator=DummyOrchestrator(),  # type: ignore[arg-type]
        )

        with patch.object(adapter, "_build_application") as build_application:
            adapter.start_polling()

        build_application.assert_not_called()
        self.assertIsNone(adapter._polling_thread)


if __name__ == "__main__":
    unittest.main()
