from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from greennode_agentbase import PingStatus, RequestContext

from marker_checker_agent.adapters.telegram_adapter import TelegramAdapter
from marker_checker_agent.ai_input_assistance import build_input_assistant
from marker_checker_agent.config import RuntimeConfig, load_runtime_config
from marker_checker_agent.orchestrator import AgentOrchestrator, MessageSource
from marker_checker_agent.persistence import build_workflow_store
from marker_checker_agent.services.audit_service import AuditService
from marker_checker_agent.services.request_service import RequestService


logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)


class MarkerCheckerRuntime:
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
        self._orchestrator = AgentOrchestrator(
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

    def start_background_services(self) -> None:
        if self._config.telegram.enabled and self._config.telegram.polling_enabled:
            self._telegram_adapter.start_polling()

    def handle_invocation(self, *, payload: dict[str, Any], context: RequestContext) -> dict:
        operation = payload.get("operation", "request_message")
        actor_name = payload.get("actor_name")
        actor_handle = payload.get("actor_handle") or getattr(context, "user_id", None) or "api-user"
        source = MessageSource(
            source_channel=payload.get("source_channel", "api"),
            channel_id=payload.get("channel_id"),
            thread_id=payload.get("thread_id"),
            source_message_id=payload.get("source_message_id"),
        )

        if operation == "request_message":
            return self._orchestrator.handle_requester_message(
                text=payload.get("message", ""),
                requester_name=actor_name,
                requester_handle=actor_handle,
                source=source,
            )

        normalized_operation = {
            "need_info": "needinfo",
            "show_request": "lookup",
            "my_approvals": "pending_approvals",
        }.get(operation, operation)

        if normalized_operation in {"approve", "reject", "needinfo", "cancel"}:
            return self._orchestrator.handle_approver_action(
                action=normalized_operation,
                request_id=payload.get("request_id", ""),
                actor_name=actor_name,
                actor_handle=actor_handle,
                note=payload.get("note", ""),
                source=source,
            )

        if normalized_operation == "resubmit":
            return self._orchestrator.handle_resubmission(
                request_id=payload.get("request_id", ""),
                text=payload.get("message", ""),
                actor_name=actor_name,
                actor_handle=actor_handle,
                source=source,
            )

        if normalized_operation == "lookup":
            return self._orchestrator.lookup_request(
                request_id=payload.get("request_id", ""),
                actor_handle=actor_handle,
            )

        if normalized_operation == "history":
            return self._orchestrator.get_history(payload.get("request_id", ""))

        if normalized_operation == "my_pending":
            return self._orchestrator.list_requester_pending(actor_handle)

        if normalized_operation == "pending_approvals":
            return self._orchestrator.list_pending_approvals(actor_handle)

        return {
            "status": "error",
            "message": f"Unsupported operation: {operation}",
        }

    def health_check(self) -> PingStatus:
        return PingStatus.HEALTHY
