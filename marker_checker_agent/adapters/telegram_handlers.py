from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from telegram.constants import ChatAction

from marker_checker_agent.domain.enums import Operation
from marker_checker_agent.domain.models import ActorContext, MessageSource, WorkflowAction

if TYPE_CHECKING:
    import threading

    from cachetools import LRUCache
    from telegram import Update
    from telegram.ext import ContextTypes

    from marker_checker_agent.domain.models import CoordinatorResponse
    from marker_checker_agent.request_coordinator import RequestCoordinator

LOGGER = logging.getLogger(__name__)

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


def _format_response_text(response: CoordinatorResponse) -> str:
    if message := response.get("message"):
        return str(message)
    if summary := response.get("summary_message"):
        return str(summary)
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


def _user_name(update: Update) -> str | None:
    user = update.effective_user
    return user.full_name if user else None


class TelegramCommandsMixin:
    if TYPE_CHECKING:
        _orchestrator: RequestCoordinator
        _chat_registry: LRUCache[str, str]
        _registry_lock: threading.Lock

    async def _reply(self, update: Update, response: CoordinatorResponse) -> None:
        if update.effective_message is None:
            return
        text = _format_response_text(response)
        if len(text) > _MAX_MSG_LEN:
            text = text[: _MAX_MSG_LEN - 6] + "\n[…]"
        await update.effective_message.reply_text(text)

    def _register_user(self, update: Update) -> None:
        user = update.effective_user
        chat = update.effective_chat
        if not user or not chat:
            return
        chat_id = str(chat.id)
        with self._registry_lock:
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

    # --- command handlers ---

    async def _help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
        await update.effective_message.reply_text(_HELP_TEXT, parse_mode="HTML")

    async def _confirm_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        requester = ActorContext(name=_user_name(update) or "", handle=self._user_handle(update))
        response = await asyncio.to_thread(
            self._orchestrator.handle_requester_message,
            text="/confirm",
            requester=requester,
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _discard_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
        response = self._orchestrator.discard_draft(self._user_handle(update))
        await self._reply(update, response)

    async def _resubmit_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
        if not context.args or len(context.args) < 2:
            await update.effective_message.reply_text(
                "Usage: /resubmit REQ-XXXX <updated request message>"
            )
            return
        request_id = context.args[0]
        text = " ".join(context.args[1:])
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        actor = ActorContext(name=_user_name(update) or "", handle=self._user_handle(update))
        response = await asyncio.to_thread(
            self._orchestrator.handle_resubmission,
            request_id=request_id,
            text=text,
            actor=actor,
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _mypending_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
        response = await asyncio.to_thread(
            self._orchestrator.list_requester_pending, self._user_handle(update)
        )
        await self._reply(update, response)

    async def _myapprovals_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
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
        if update.effective_message is None:
            return
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
        if update.effective_message is None:
            return
        if not context.args:
            await update.effective_message.reply_text("Usage: /history REQ-XXXX")
            return
        response = await asyncio.to_thread(self._orchestrator.get_history, context.args[0])
        await self._reply(update, response)

    async def _search_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
        if not context.args:
            await update.effective_message.reply_text("Usage: /search <target name>")
            return
        query = " ".join(context.args)
        response = await asyncio.to_thread(self._orchestrator.search_by_target, query)
        await self._reply(update, response)

    async def _text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        self._register_user(update)
        if update.effective_message is None:
            return
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        text: str = update.effective_message.text or ""
        requester = ActorContext(name=_user_name(update) or "", handle=self._user_handle(update))
        response = await asyncio.to_thread(
            self._orchestrator.handle_requester_message,
            text=text,
            requester=requester,
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
        if update.effective_message is None:
            return
        if not context.args:
            await update.effective_message.reply_text(
                f"Usage: /{action} REQ-XXXX [optional note]"
            )
            return
        request_id = context.args[0]
        note = " ".join(context.args[1:]).strip()
        await update.effective_message.chat.send_action(ChatAction.TYPING)
        actor = ActorContext(name=_user_name(update) or "", handle=self._user_handle(update))
        workflow_action = WorkflowAction(action=action, request_id=request_id, note=note)
        response = await asyncio.to_thread(
            self._orchestrator.handle_approver_action,
            actor=actor,
            action=workflow_action,
            source=self._source_from_update(update),
        )
        await self._reply(update, response)

    async def _handle_callback_query(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        query = update.callback_query
        if query is None:
            return
        await query.answer()
        self._register_user(update)

        data = query.data
        if not isinstance(data, str):
            await query.edit_message_text("Invalid action data.")
            return
        parts = data.split(":", 1)
        if len(parts) != 2:
            await query.edit_message_text("Invalid action data.")
            return
        action_str, request_id = parts
        try:
            action = Operation(action_str)
        except ValueError:
            await query.edit_message_text("Unknown action.")
            return

        actor = ActorContext(name=_user_name(update) or "", handle=self._user_handle(update))
        workflow_action = WorkflowAction(action=action, request_id=request_id, note="")
        response = await asyncio.to_thread(
            self._orchestrator.handle_approver_action,
            actor=actor,
            action=workflow_action,
            source=self._source_from_update(update),
        )
        text = _format_response_text(response)
        if len(text) > _MAX_MSG_LEN:
            text = text[: _MAX_MSG_LEN - 6] + "\n[…]"
        await query.edit_message_text(text=text, reply_markup=None)
