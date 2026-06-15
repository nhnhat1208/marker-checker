from __future__ import annotations

import asyncio
import logging
import threading
from typing import TYPE_CHECKING, Any

from cachetools import LRUCache
from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from marker_checker_agent.adapters.telegram_handlers import TelegramCommandsMixin

if TYPE_CHECKING:
    from marker_checker_agent.config import TelegramConfig
    from marker_checker_agent.domain.models import RequestSummary
    from marker_checker_agent.request_coordinator import RequestCoordinator

BotApplication = Application[Any, Any, Any, Any, Any, Any]

LOGGER = logging.getLogger(__name__)

# Callback data prefixes for inline keyboard buttons.
_CB_APPROVE = "approve"
_CB_REJECT = "reject"
_CB_NEEDINFO = "needinfo"


def _approver_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"{_CB_APPROVE}:{request_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"{_CB_REJECT}:{request_id}"),
        InlineKeyboardButton("❓ Need Info", callback_data=f"{_CB_NEEDINFO}:{request_id}"),
    ]])


class TelegramAdapter(TelegramCommandsMixin):
    def __init__(
        self,
        *,
        config: TelegramConfig,
        orchestrator: RequestCoordinator,
    ) -> None:
        self._config = config
        self._orchestrator = orchestrator
        self._application: BotApplication | None = None
        self._polling_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        # Maps @handle / telegram:<id> → Telegram chat_id string.
        # LRUCache: caps memory at 4096 user entries; no TTL needed (chat IDs don't expire).
        # _registry_lock: LRUCache is not thread-safe; notify_approver is called from a
        # thread-pool thread (asyncio.to_thread) while _register_user runs on the event loop.
        self._chat_registry: LRUCache[str, str] = LRUCache(maxsize=4096)
        self._registry_lock = threading.Lock()

    def start_polling(self) -> None:
        if not self._config.enabled:
            LOGGER.info("Telegram adapter is disabled.")
            return

        bot_token = self._config.bot_token.strip()
        if not bot_token:
            LOGGER.warning("Telegram bot token is not configured. Polling will not start.")
            return

        if self._polling_thread and self._polling_thread.is_alive():
            return

        self._application = self._build_application(bot_token)
        self._polling_thread = threading.Thread(target=self._run_polling, daemon=True)
        self._polling_thread.start()
        LOGGER.info("Telegram polling thread started.")

    def notify_approver(self, payload: RequestSummary) -> None:
        approver_handle = payload.get("approver_handle", "")
        with self._registry_lock:
            chat_id = self._chat_registry.get(approver_handle)
        if not chat_id:
            LOGGER.info(
                "notify_approver: no chat_id for %s (not yet interacted with bot)",
                approver_handle,
            )
            return
        request_id = payload.get("request_id", "")
        text = (
            f"📋 New approval request: {request_id}\n"
            f"Target:    {payload.get('target_label')}\n"
            f"From:      {payload.get('change_from_summary')}\n"
            f"To:        {payload.get('change_to_summary')}\n"
            f"Requester: {payload.get('requester_handle')}"
        )
        self._send_message(chat_id, text, reply_markup=_approver_keyboard(request_id))

    def notify_requester(self, origin_channel_id: str, message: str) -> None:
        self._send_message(origin_channel_id, message)

    def stop(self) -> None:
        app = self._application
        if app is not None:
            app.stop_running()
        thread = self._polling_thread
        if thread is not None:
            thread.join(timeout=10)

    def _send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        # Capture to locals to avoid TOCTOU: another thread could set these to None
        # between the None-check and the coroutine submission.
        loop = self._loop
        app = self._application
        if app is None or loop is None or not loop.is_running():
            LOGGER.info("_send_message: event loop not available, message not sent to %s", chat_id)
            return
        future = asyncio.run_coroutine_threadsafe(
            app.bot.send_message(chat_id=chat_id, text=text, reply_markup=reply_markup),
            loop,
        )
        future.add_done_callback(
            lambda f: LOGGER.warning("_send_message failed chat_id=%s error=%s", chat_id, f.exception())
            if f.exception() else None
        )

    def _build_application(self, bot_token: str) -> BotApplication:
        application = (
            ApplicationBuilder()
            .token(bot_token)
            .post_init(self._post_init)
            .build()
        )
        application.add_handler(CommandHandler("start", self._help_command))
        application.add_handler(CommandHandler("help", self._help_command))
        application.add_handler(CommandHandler("confirm", self._confirm_command))
        application.add_handler(CommandHandler("discard", self._discard_command))
        application.add_handler(CommandHandler("resubmit", self._resubmit_command))
        application.add_handler(CommandHandler("mypending", self._mypending_command))
        application.add_handler(CommandHandler("requests", self._requests_command))
        application.add_handler(CommandHandler("myapprovals", self._myapprovals_command))
        application.add_handler(CommandHandler("approvals", self._approvals_command))
        application.add_handler(CommandHandler("approve", self._approve_command))
        application.add_handler(CommandHandler("reject", self._reject_command))
        application.add_handler(CommandHandler("needinfo", self._needinfo_command))
        application.add_handler(CommandHandler("cancel", self._cancel_command))
        application.add_handler(CommandHandler("status", self._status_command))
        application.add_handler(CommandHandler("history", self._history_command))
        application.add_handler(CommandHandler("search", self._search_command))
        application.add_handler(
            CallbackQueryHandler(
                self._handle_callback_query,
                pattern=r"^(approve|reject|needinfo|confirm|cancel):.+$",
            )
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._text_message)
        )
        application.add_error_handler(self._error_handler)
        return application

    def _run_polling(self) -> None:
        import time
        from telegram.error import Conflict

        if self._application is None:
            return

        # During rolling deploys the old container keeps polling until the platform
        # terminates it.  When the new container starts and gets a 409 Conflict it
        # rebuilds the Application and retries; the old container is typically gone
        # within 30 s.
        _CONFLICT_RETRY_INTERVAL = 10   # seconds between retries
        _CONFLICT_MAX_RETRIES    = 18   # 18 × 10 s = 3 min ceiling

        bot_token = self._config.bot_token.strip()

        for attempt in range(_CONFLICT_MAX_RETRIES + 1):
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            self._loop = loop
            conflict = False
            try:
                self._application.run_polling(
                    drop_pending_updates=True,
                    close_loop=False,
                    stop_signals=None,
                )
                return  # clean exit — stop retrying
            except Conflict:
                conflict = True
                if attempt < _CONFLICT_MAX_RETRIES:
                    LOGGER.warning(
                        "Telegram polling conflict (another instance still running) — "
                        "retrying in %ds (attempt %d/%d)",
                        _CONFLICT_RETRY_INTERVAL, attempt + 1, _CONFLICT_MAX_RETRIES,
                    )
                else:
                    LOGGER.error(
                        "Telegram polling conflict persists after %d retries — giving up",
                        _CONFLICT_MAX_RETRIES,
                    )
            finally:
                self._loop = None
                try:
                    loop.run_until_complete(loop.shutdown_asyncgens())
                finally:
                    asyncio.set_event_loop(None)
                    loop.close()

            if conflict and attempt < _CONFLICT_MAX_RETRIES:
                time.sleep(_CONFLICT_RETRY_INTERVAL)
                # Rebuild a fresh Application — PTB internal state may be partial after a
                # failed run_polling.
                self._application = self._build_application(bot_token)

    async def _post_init(self, application: BotApplication) -> None:
        await application.bot.set_my_commands([
            BotCommand("start", "Show usage guide"),
            BotCommand("help", "Show usage guide"),
            BotCommand("confirm", "Submit the pending draft"),
            BotCommand("discard", "Cancel the pending draft"),
            BotCommand("resubmit", "Revise and resubmit after Need Info"),
            BotCommand("mypending", "List your active requests"),
            BotCommand("requests", "List your active requests"),
            BotCommand("myapprovals", "List requests waiting for your approval"),
            BotCommand("approvals", "List requests waiting for your approval"),
            BotCommand("approve", "Approve a request"),
            BotCommand("reject", "Reject a request"),
            BotCommand("needinfo", "Ask requester for more information"),
            BotCommand("cancel", "Cancel a request"),
            BotCommand("status", "View request details"),
            BotCommand("history", "View request event timeline"),
            BotCommand("search", "Search requests by target name"),
        ])
