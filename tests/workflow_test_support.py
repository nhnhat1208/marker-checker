from __future__ import annotations

import unittest
from uuid import uuid4

from marker_checker_agent.config import RuntimeConfig
from marker_checker_agent.domain.models import (
    AuditEventRecord,
    RequestConversationRecord,
    RequestRecord,
)
from marker_checker_agent.orchestrator import AgentOrchestrator, MessageSource
from marker_checker_agent.services.audit_service import AuditService
from marker_checker_agent.services.request_service import RequestService


class InMemoryWorkflowStore:
    def __init__(self) -> None:
        self.requests: dict[str, RequestRecord] = {}
        self.audit_events: dict[str, list[AuditEventRecord]] = {}
        self.request_conversations: list[RequestConversationRecord] = []

    def initialize(self) -> None:
        return None

    def create_request(self, request: RequestRecord) -> RequestRecord:
        self.requests[request.request_id] = request
        return request

    def update_request(self, request: RequestRecord) -> RequestRecord:
        self.requests[request.request_id] = request
        return request

    def get_request(self, request_id: str) -> RequestRecord | None:
        return self.requests.get(request_id)

    def list_requests(self) -> list[RequestRecord]:
        return list(self.requests.values())

    def create_request_conversation(
        self,
        conversation: RequestConversationRecord,
    ) -> RequestConversationRecord:
        if not conversation.row_id:
            conversation.row_id = uuid4().hex
        self.request_conversations.append(conversation)
        return conversation

    def create_audit_event(self, event: AuditEventRecord) -> AuditEventRecord:
        if not event.event_id:
            event.event_id = uuid4().hex

        events = self.audit_events.setdefault(event.request_id, [])
        if event.event_sequence <= 0:
            event.event_sequence = len(events) + 1
        events.append(event)
        return event

    def list_audit_events(self, request_id: str) -> list[AuditEventRecord]:
        return list(self.audit_events.get(request_id, []))


class WorkflowTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.store = InMemoryWorkflowStore()
        self.audit_service = AuditService(self.store)
        self.config = RuntimeConfig(app={"request_id_prefix": "SMK"})
        self.request_service = RequestService(
            config=self.config,
            workflow_store=self.store,
            audit_service=self.audit_service,
        )
        self.orchestrator = AgentOrchestrator(
            request_service=self.request_service,
            audit_service=self.audit_service,
        )
        self.notifications: list[dict] = []
        self.orchestrator.set_approver_notification_callback(self.notifications.append)
        self.source = MessageSource(
            source_channel="test",
            channel_id="local-chat",
            thread_id="local-thread",
            source_message_id="msg-1",
        )
