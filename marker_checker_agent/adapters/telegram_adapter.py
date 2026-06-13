from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from cachetools import LRUCache

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from marker_checker_agent.config import TelegramConfig
from marker_checker_agent.domain.enums import Operation
from marker_checker_agent.orchestrator import AgentOrchestrator, MessageSource


LOGGER = logging.getLogger(__name__)

# Callback data prefixes for inline keyboard buttons.
_CB_APPROVE = "approve"
_CB_REJECT = "reject"
_CB_NEEDINFO = "needinfo"


def _format_response_text(response: dict) -> str:
    if message := response.get("message"):
        return message
    if summary := response.get("summary_message"):
        return summary
    if request := response.get("request"):
        return "\n".join([
            f"request_id: {request.get('request_id')}",
            f"status:     {request.get('review_status')}",
            f"target:     {request.get('target_label')}",
            f"from:       {request.get('change_from_summary')}",
            f"to:         {request.get('change_to_summary')}",
        ])
    if timeline := response.get("timeline"):
        lines = [
            f"{item['event_sequence']}. {item['event_type']} — {item['summary']}"
            for item in timeline
        ]
        return "\n".join(lines) or "No history."
    return "No response payload available."


def _approver_keyboard(request_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ Approve", callback_data=f"{_CB_APPROVE}:{request_id}"),
        InlineKeyboardButton("❌ Reject", callback_data=f"{_CB_REJECT}:{request_id}"),
        InlineKeyboardButton("❓ Need Info", callback_data=f"{_CB_NEEDINFO}:{request_id}"),
    ]])


_MAX_MSG_LEN = 4096

_HELP_TEXT = (
    "<b>🤖 Marker Checker</b> — Change Request Approval Agent\n\n"
    "Send a message in plain text (Vietnamese or English) to create a request. "
    "The agent will parse it and ask you to confirm before submitting.\n\n"
    "<b>Example messages:</b>\n"
    "• <code>enable feature-X on api-gateway, ask @john to approve</code>\n"
    "• <code>tắt tính năng beta trên nginx, nhờ @manager duyệt</code>\n"
    "• <code>change timeout from 30s to 60s for nginx-config, @ops should review</code>\n\n"
    "─────────────────────────────\n"
    "<b>Requester commands</b>\n\n"
    "/confirm — Confirm and submit the pending draft\n"
    "/discard — Cancel the pending draft without submitting\n"
    "/resubmit <code>REQ-XXXX &lt;new message&gt;</code> — Revise and resubmit after Need Info\n"
    "/mypending — List your active requests\n"
    "/status <code>REQ-XXXX</code> — View current status and details\n"
    "/history <code>REQ-XXXX</code> — View the full event timeline\n"
    "/search <code>&lt;query&gt;</code> — Search requests by target name\n\n"
    "─────────────────────────────\n"
    "<b>Approver commands</b>\n\n"
    "/myapprovals — List requests waiting for your approval\n"
    "/approve <code>REQ-XXXX [note]</code> — Approve a request\n"
    "/reject <code>REQ-XXXX [reason]</code> — Reject a request\n"
    "/needinfo <code>REQ-XXXX [question]</code> — Ask requester for more information\n"
    "/cancel <code>REQ-XXXX [note]</code> — Cancel a request\n\n"
    "─────────────────────────────\n"
    "<b>Workflow</b>\n\n"
    "1. Requester sends a change description → agent drafts a request\n"
    "2. Requester sends /confirm → submitted, approver notified\n"
    "3. Approver taps inline buttons or uses /approve, /reject, /needinfo\n"
    "4. Requester is notified of the decision\n"
    "5. If needinfo: requester uses /resubmit to revise and resubmit"
)


def _user_name(update: Update) -> str | None:
    user = update.effective_user
    return user.full_name if user else None


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
        self._loop: asyncio.AbstractEventLoop | None = None
        # Maps @handle / telegram:<id> → Telegram chat_id string.
        # LRUCache: caps memory at 4096 user entries; no TTL needed (chat IDs don't expire).
        self._chat_registry: LRUCache[str, str] = LRUCache(maxsize=4096)

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

    def notify_approver(self, payload: dict[str, Any]) -> None:
        approver_handle = payload.get("approver_handle", "")
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

    def _send_message(
        self,
        chat_id: str,
        text: str,
        reply_markup: InlineKeyboardMarkup | None = None,
    ) -> None:
        if not self._application or not self._loop or not self._loop.is_running():
            LOGGER.info("_send_message: event loop not available, message not sent to %s", chat_id)
            return
        asyncio.run_coroutine_threadsafe(
            self._application.bot.send_message(
                chat_id=chat_id, text=text, reply_markup=reply_markup
            ),
            self._loop,
        )

    def _build_application(self, bot_token: str) -> Application:
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
        application.add_handler(CommandHandler("myapprovals", self._myapprovals_command))
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
                pattern=r"^(approve|reject|needinfo):.+$",
            )
        )
        application.add_handler(
            MessageHandler(filters.TEXT & ~filters.COMMAND, self._text_message)
        )
        return application

    def _run_polling(self) -> None:
        if self._application is None:
            return
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        try:
            self._application.run_polling(
                drop_pending_updates=True,
                close_loop=False,
                stop_signals=None,
            )
        finally:
            self._loop = None
            try:
                loop.run_until_complete(loop.shutdown_asyncgens())
            finally:
                asyncio.set_event_loop(None)
                loop.close()

    async def _post_init(self, application: Application) -> None:
        await application.bot.set_my_commands([
            BotCommand("start", "Show usage guide"),
            BotCommand("help", "Show usage guide"),
            BotCommand("confirm", "Submit the pending draft"),
            BotCommand("discard", "Cancel the pending draft"),
            BotCommand("resubmit", "Revise and resubmit after Need Info"),
            BotCommand("mypending", "List your active requests"),
            BotCommand("myapprovals", "List requests waiting for your approval"),
            BotCommand("approve", "Approve a request"),
            BotCommand("reject", "Reject a request"),
            BotCommand("needinfo", "Ask requester for more information"),
            BotCommand("cancel", "Cancel a request"),
            BotCommand("status", "View request details"),
            BotCommand("history", "View request event timeline"),
            BotCommand("search", "Search requests by target name"),
        ])

    # --- command handlers ---

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        await update.effective_message.reply_text(_HELP_TEXT, parse_mode="HTML")

    async def _confirm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        response = await asyncio.to_thread(
            self._orchestrator.handle_requester_message,
            text="/confirm",
            requester_name=_user_name(update),
            requester_handle=self._user_handle(update),
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _discard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        response = self._orchestrator.discard_draft(self._user_handle(update))
        await self._reply(update, response)

    async def _resubmit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if not context.args or len(context.args) < 2:
            await update.effective_message.reply_text(
                "Usage: /resubmit REQ-XXXX <updated request message>"
            )
            return
        request_id = context.args[0]
        text = " ".join(context.args[1:])
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        response = await asyncio.to_thread(
            self._orchestrator.handle_resubmission,
            request_id=request_id,
            text=text,
            actor_name=_user_name(update),
            actor_handle=self._user_handle(update),
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _mypending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        response = await asyncio.to_thread(
            self._orchestrator.list_requester_pending, self._user_handle(update)
        )
        await self._reply(update, response)

    async def _myapprovals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        response = await asyncio.to_thread(
            self._orchestrator.list_pending_approvals, self._user_handle(update)
        )
        await self._reply(update, response)

    async def _approve_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action=Operation.APPROVE)

    async def _reject_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action=Operation.REJECT)

    async def _needinfo_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action=Operation.NEEDINFO)

    async def _cancel_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await self._handle_action_command(update, context, action=Operation.CANCEL)

    async def _status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if not context.args:
            await update.effective_message.reply_text("Usage: /status REQ-XXXX")
            return
        response = await asyncio.to_thread(
            self._orchestrator.lookup_request,
            request_id=context.args[0],
            actor_handle=self._user_handle(update),
        )
        await self._reply(update, response)

    async def _history_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if not context.args:
            await update.effective_message.reply_text("Usage: /history REQ-XXXX")
            return
        response = await asyncio.to_thread(self._orchestrator.get_history, context.args[0])
        await self._reply(update, response)

    async def _search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if not context.args:
            await update.effective_message.reply_text("Usage: /search <target name>")
            return
        query = " ".join(context.args)
        response = await asyncio.to_thread(self._orchestrator.search_by_target, query)
        await self._reply(update, response)

    async def _text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        text = update.effective_message.text if update.effective_message else ""
        response = await asyncio.to_thread(
            self._orchestrator.handle_requester_message,
            text=text,
            requester_name=_user_name(update),
            requester_handle=self._user_handle(update),
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _handle_action_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        *,
        action: Operation,
    ) -> None:
        self._register_user(update)
        if not context.args:
            await update.effective_message.reply_text(
                f"Usage: /{action} REQ-XXXX [optional note]"
            )
            return
        request_id = context.args[0]
        note = " ".join(context.args[1:]).strip()
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        response = await asyncio.to_thread(
            self._orchestrator.handle_approver_action,
            action=action,
            request_id=request_id,
            actor_name=_user_name(update),
            actor_handle=self._user_handle(update),
            note=note,
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        await query.answer()
        self._register_user(update)

        parts = query.data.split(":", 1)
        if len(parts) != 2:
            await query.edit_message_text("Invalid action data.")
            return
        action_str, request_id = parts
        try:
            action = Operation(action_str)
        except ValueError:
            await query.edit_message_text("Unknown action.")
            return

        response = await asyncio.to_thread(
            self._orchestrator.handle_approver_action,
            action=action,
            request_id=request_id,
            actor_name=_user_name(update),
            actor_handle=self._user_handle(update),
            note="",
            source=self._source_from_update(update),
        )
        await query.edit_message_text(
            text=_format_response_text(response),
            reply_markup=None,
        )

    async def _reply(self, update: Update, response: dict) -> None:
        text = _format_response_text(response)
        if len(text) > _MAX_MSG_LEN:
            text = text[: _MAX_MSG_LEN - 6] + "\n[…]"
        await update.effective_message.reply_text(text)

    # --- private helpers ---

    def _register_user(self, update: Update) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return
        chat_id = str(chat.id)
        if user.username:
            self._chat_registry[f"@{user.username}"] = chat_id
        self._chat_registry[f"telegram:{user.id}"] = chat_id

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
