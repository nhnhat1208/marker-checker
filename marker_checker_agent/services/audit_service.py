from __future__ import annotations

from typing import TYPE_CHECKING, Literal, cast

from marker_checker_agent.domain.models import (
    ActorContext,
    AuditEventInput,
    AuditEventRecord,
    MessageSource,
)

if TYPE_CHECKING:
    from marker_checker_agent.persistence.base import WorkflowStore


class AuditService:
    def __init__(self, workflow_store: WorkflowStore) -> None:
        self._workflow_store = workflow_store

    def record_event(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        event: AuditEventInput,
    ) -> AuditEventRecord:
        src = event.source or MessageSource()
        evt = AuditEventRecord(
            request_id=request_id,
            event_type=event.event_type,
            actor_name=actor.name,
            actor_handle=actor.handle,
            actor_kind=event.actor_kind,
            request_revision=event.request_revision,
            summary=event.summary,
            event_payload=event.event_payload or {},
            source_channel=cast("Literal['telegram']", src.source_channel),
            thread_id=src.thread_id,
            source_message_id=src.source_message_id,
        )
        return self._workflow_store.create_audit_event(evt)

    def list_timeline(self, request_id: str) -> list[AuditEventRecord]:
        return self._workflow_store.list_audit_events(request_id)
