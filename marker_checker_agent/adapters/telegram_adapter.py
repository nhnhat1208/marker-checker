from __future__ import annotations

import asyncio
import logging
import threading

from telegram import Update
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from marker_checker_agent.config import TelegramConfig
from marker_checker_agent.orchestrator import AgentOrchestrator, MessageSource


LOGGER = logging.getLogger(__name__)


class TelegramAdapter:
    def __init__(
        self,
        *,
        config: TelegramConfig,
        orchestrator: AgentOrchestrator,
    ) -> None:
        self._config = config
        self._orchestrator = orchestrator
        self._application: Application | None = None
        self._polling_thread: threading.Thread | None = None

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

    def notify_approver(self, payload: dict) -> None:
        LOGGER.info(
            "Approver notification placeholder for %s on %s",
            payload.get("approver_handle"),
            payload.get("request_id"),
        )

    def _build_application(self, bot_token: str) -> Application:
        application = ApplicationBuilder().token(bot_token).build()
        application.add_handler(CommandHandler("confirm", self._confirm_command))
        application.add_handler(CommandHandler("approve", self._approve_command))
        application.add_handler(CommandHandler("reject", self._reject_command))
        application.add_handler(CommandHandler("needinfo", self._needinfo_command))
        application.add_handler(CommandHandler("cancel", self._cancel_command))
        application.add_handler(CommandHandler("status", self._status_command))
        application.add_handler(CommandHandler("history", self._history_command))
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._text_message)
        )
        return application

    def _run_polling(self) -> None:
        if self._application is None:
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            self._application.run_polling(
                drop_pending_updates=True,
                close_loop=False,
                stop_signals=None,
            )
        finally:
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                asyncio.set_event_loop(None)
                loop.close()

    async def _confirm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        response = self._orchestrator.handle_requester_message(
            text="/confirm",
            requester_name=update.effective_user.full_name if update.effective_user else None,
            requester_handle=self._user_handle(update),
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _approve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action="approve")

    async def _reject_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action="reject")

    async def _needinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action="needinfo")

    async def _cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action="cancel")

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.effective_message.reply_text("Usage: /status REQ-XXXX")
            return

        response = self._orchestrator.lookup_request(
            request_id=context.args[0],
            actor_handle=self._user_handle(update),
        )
        await self._reply(update, response)

    async def _history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not context.args:
            await update.effective_message.reply_text("Usage: /history REQ-XXXX")
            return

        response = self._orchestrator.get_history(context.args[0])
        await self._reply(update, response)

    async def _text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        text = update.effective_message.text if update.effective_message else ""
        response = self._orchestrator.handle_requester_message(
            text=text,
            requester_name=update.effective_user.full_name if update.effective_user else None,
            requester_handle=self._user_handle(update),
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _handle_action_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *,
        action: str,
    ) -> None:
        if not context.args:
            await update.effective_message.reply_text(
                f"Usage: /{action} REQ-XXXX optional note"
            )
            return

        request_id = context.args[0]
        note = " ".join(context.args[1:]).strip()
        response = self._orchestrator.handle_approver_action(
            action=action,
            request_id=request_id,
            actor_name=update.effective_user.full_name if update.effective_user else None,
            actor_handle=self._user_handle(update),
            note=note,
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _reply(self, update: Update, response: dict) -> None:
        message = response.get("message")
        if message:
            await update.effective_message.reply_text(message)
            return

        summary_message = response.get("summary_message")
        if summary_message:
            await update.effective_message.reply_text(summary_message)
            return

        if "request" in response:
            request = response["request"]
            await update.effective_message.reply_text(
                "\n".join(
                    [
                        f"request_id: {request.get('request_id')}",
                        f"status: {request.get('review_status')}",
                        f"target: {request.get('target_label')}",
                        f"from: {request.get('change_from_summary')}",
                        f"to: {request.get('change_to_summary')}",
                    ]
                )
            )
            return

        if "timeline" in response:
            lines = [
                f"{item['event_sequence']}. {item['event_type']} - {item['summary']}"
                for item in response["timeline"]
            ]
            await update.effective_message.reply_text("\n".join(lines) or "No history.")
            return

        await update.effective_message.reply_text("No response payload available.")

    def _source_from_update(self, update: Update) -> MessageSource:
        chat_id = str(update.effective_chat.id) if update.effective_chat else None
        message_id = (
            str(update.effective_message.message_id) if update.effective_message else None
        )
        return MessageSource(
            source_channel="telegram",
            channel_id=chat_id,
            thread_id=chat_id,
            source_message_id=message_id,
        )

    def _user_handle(self, update: Update) -> str:
        user = update.effective_user
        if user is None:
            return "unknown-user"
        if user.username:
            return f"@{user.username}"
        return f"telegram:{user.id}"
