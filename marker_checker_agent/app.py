from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from greennode_agentbase import PingStatus, RequestContext

from marker_checker_agent.adapters.telegram_adapter import TelegramAdapter
from marker_checker_agent.ai.assistant import build_input_assistant
from marker_checker_agent.config import RuntimeConfig, load_runtime_config
from marker_checker_agent.domain.enums import Operation
from marker_checker_agent.domain.models import (
    ActorContext,
    CoordinatorResponse,
    MessageSource,
    WorkflowAction,
)
from marker_checker_agent.persistence.factory import build_workflow_store
from marker_checker_agent.request_coordinator import RequestCoordinator
from marker_checker_agent.services.audit_service import AuditService
from marker_checker_agent.services.request_service import RequestService

LOGGER = logging.getLogger(__name__)

# String aliases for operation names that differ from the enum value.
_OPERATION_ALIASES: dict[str, str] = {
    "need_info": Operation.NEEDINFO.value,
    "show_request": Operation.LOOKUP.value,
    "my_approvals": Operation.PENDING_APPROVALS.value,
}

# Operations routed to handle_approver_action.
_APPROVER_ACTIONS: frozenset[Operation] = frozenset({
    Operation.APPROVE,
    Operation.REJECT,
    Operation.NEEDINFO,
    Operation.CANCEL,
})


class MarkerCheckerApp:
    def __init__(self, base_dir: Path | None = None) -> None:
        self._base_dir = base_dir or Path.cwd()
        self._config: RuntimeConfig = load_runtime_config(self._base_dir)
        self._workflow_store = build_workflow_store(self._config)
        self._workflow_store.initialize()
        self._audit_service = AuditService(self._workflow_store)
        self._request_service = RequestService(
            config=self._config,
            workflow_store=self._workflow_store,
            audit_service=self._audit_service,
        )
        self._input_assistant = build_input_assistant(self._config.ai)
        self._orchestrator = RequestCoordinator(
            request_service=self._request_service,
            audit_service=self._audit_service,
            input_assistant=self._input_assistant,
        )
        self._telegram_adapter = TelegramAdapter(
            config=self._config.telegram,
            orchestrator=self._orchestrator,
        )
        self._orchestrator.set_approver_notification_callback(
            self._telegram_adapter.notify_approver
        )
        self._orchestrator.set_requester_notification_callback(
            self._telegram_adapter.notify_requester
        )

    def start_background_services(self) -> None:
        if self._config.telegram.enabled and self._config.telegram.polling_enabled:
            self._telegram_adapter.start_polling()

    def handle_invocation(self, *, payload: dict[str, Any], context: RequestContext) -> CoordinatorResponse:
        raw_op = payload.get("operation", "request_message")
        actor_name: str = payload.get("actor_name") or ""
        actor_handle: str = payload.get("actor_handle") or context.user_id or "api-user"
        source = MessageSource(
            source_channel=payload.get("source_channel", "telegram"),
            channel_id=payload.get("channel_id"),
            thread_id=payload.get("thread_id"),
            source_message_id=payload.get("source_message_id"),
        )

        # Free-text message from requester — not mapped to an Operation enum.
        if raw_op == "request_message":
            return self._orchestrator.handle_requester_message(
                text=payload.get("message", ""),
                requester=ActorContext(name=actor_name, handle=actor_handle),
                source=source,
            )

        # Resolve alias (e.g. "need_info" → "needinfo") then parse to Operation enum.
        resolved = _OPERATION_ALIASES.get(raw_op, raw_op)
        try:
            op = Operation(resolved)
        except ValueError:
            return {"status": "error", "message": f"Unsupported operation: {raw_op!r}"}

        if op in _APPROVER_ACTIONS:
            return self._orchestrator.handle_approver_action(
                actor=ActorContext(name=actor_name, handle=actor_handle),
                action=WorkflowAction(
                    action=op,
                    request_id=payload.get("request_id", ""),
                    note=payload.get("note", ""),
                ),
                source=source,
            )

        if op == Operation.RESUBMIT:
            return self._orchestrator.handle_resubmission(
                request_id=payload.get("request_id", ""),
                text=payload.get("message", ""),
                actor=ActorContext(name=actor_name, handle=actor_handle),
                source=source,
            )

        if op == Operation.LOOKUP:
            return self._orchestrator.lookup_request(
                request_id=payload.get("request_id", ""),
                actor_handle=actor_handle,
            )

        if op == Operation.HISTORY:
            return self._orchestrator.get_history(payload.get("request_id", ""))

        if op == Operation.MY_PENDING:
            return self._orchestrator.list_requester_pending(actor_handle)

        if op == Operation.PENDING_APPROVALS:
            return self._orchestrator.list_pending_approvals(actor_handle)

        return {"status": "error", "message": f"Unsupported operation: {raw_op!r}"}

    def stop(self) -> None:
        self._telegram_adapter.stop()

    def health_check(self) -> PingStatus:
        return PingStatus.HEALTHY
