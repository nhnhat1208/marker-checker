from __future__ import annotations

from typing import Protocol

from marker_checker_agent.domain.models import (
    AuditEventRecord,
    RequestConversationRecord,
    RequestRecord,
)


class WorkflowStore(Protocol):
    def initialize(self) -> None:
        """Prepare the underlying storage."""

    def create_request(self, request: RequestRecord) -> RequestRecord:
        """Persist a new request."""

    def update_request(self, request: RequestRecord) -> RequestRecord:
        """Persist changes to an existing request."""

    def get_request(self, request_id: str) -> RequestRecord | None:
        """Fetch one request by ID."""

    def create_request_conversation(
        self,
        conversation: RequestConversationRecord,
    ) -> RequestConversationRecord:
        """Link a request to one actor conversation."""

    def create_audit_event(self, event: AuditEventRecord) -> AuditEventRecord:
        """Append an immutable audit event."""

    def list_audit_events(self, request_id: str) -> list[AuditEventRecord]:
        """Return the timeline for one request."""
