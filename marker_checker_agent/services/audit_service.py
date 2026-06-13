from __future__ import annotations

from typing import Any

from marker_checker_agent.domain.enums import AuditEventType
from marker_checker_agent.domain.models import AuditEventRecord
from marker_checker_agent.persistence.base import WorkflowStore


class AuditService:
    def __init__(self, workflow_store: WorkflowStore):
        self._workflow_store = workflow_store

    def record_event(
        self,
        *,
        request_id: str,
        event_type: AuditEventType,
        actor_handle: str,
        actor_name: str | None = None,
        actor_kind: str = "user",
        request_revision: int | None = None,
        summary: str = "",
        event_payload: dict[str, Any] | None = None,
        source_channel: str = "telegram",
        thread_id: str | None = None,
        source_message_id: str | None = None,
    ) -> AuditEventRecord:
        event = AuditEventRecord(
            request_id=request_id,
            event_type=event_type.value,
            actor_name=actor_name,
            actor_handle=actor_handle,
            actor_kind=actor_kind,
            request_revision=request_revision,
            summary=summary,
            event_payload=event_payload or {},
            source_channel=source_channel,
            thread_id=thread_id,
            source_message_id=source_message_id,
        )
        return self._workflow_store.create_audit_event(event)

    def list_timeline(self, request_id: str) -> list[AuditEventRecord]:
        return self._workflow_store.list_audit_events(request_id)
