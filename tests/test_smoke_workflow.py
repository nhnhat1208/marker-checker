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


class WorkflowSmokeTest(unittest.TestCase):
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

    def test_submit_approve_lookup_and_history(self) -> None:
        draft_response = self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(draft_response["status"], "confirmation_required")

        submit_response = self.orchestrator.handle_requester_message(
            text="/confirm",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(submit_response["status"], "submitted")
        request_id = submit_response["request"]["request_id"]
        self.assertTrue(request_id.startswith("SMK-"))
        self.assertEqual(len(self.notifications), 1)

        approve_response = self.orchestrator.handle_approver_action(
            action="approve",
            request_id=request_id,
            actor_name="Checker One",
            actor_handle="@checker",
            note="looks good",
            source=self.source,
        )
        self.assertEqual(approve_response["status"], "ok")
        self.assertEqual(
            approve_response["request"]["review_status"],
            "approved",
        )

        lookup_response = self.orchestrator.lookup_request(
            request_id=request_id,
            actor_handle="@auditor",
        )
        self.assertEqual(lookup_response["status"], "ok")
        self.assertEqual(lookup_response["request"]["request_id"], request_id)

        history_response = self.orchestrator.get_history(request_id)
        self.assertEqual(history_response["status"], "ok")
        event_types = [item["event_type"] for item in history_response["timeline"]]
        self.assertEqual(
            event_types,
            [
                "request_submitted",
                "approver_notified",
                "decision_recorded",
                "lookup_performed",
            ],
        )

    def test_needinfo_then_resubmit(self) -> None:
        self.orchestrator.handle_requester_message(
            text="for sample-object, change from old-state to new-state, ask @checker to approve",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        submit_response = self.orchestrator.handle_requester_message(
            text="/confirm",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        request_id = submit_response["request"]["request_id"]

        needinfo_response = self.orchestrator.handle_approver_action(
            action="needinfo",
            request_id=request_id,
            actor_name="Checker One",
            actor_handle="@checker",
            note="please clarify target state",
            source=self.source,
        )
        self.assertEqual(needinfo_response["status"], "ok")
        self.assertEqual(
            needinfo_response["request"]["review_status"],
            "needs_info",
        )

        resubmit_response = self.orchestrator.handle_resubmission(
            request_id=request_id,
            text="for sample-object, change from old-state to new-state-v2, ask @checker to approve",
            actor_name="Requester One",
            actor_handle="@requester",
            source=self.source,
        )
        self.assertEqual(resubmit_response["status"], "ok")
        self.assertEqual(
            resubmit_response["request"]["review_status"],
            "submitted",
        )
        self.assertEqual(
            resubmit_response["request"]["last_submitted_revision"],
            2,
        )


if __name__ == "__main__":
    unittest.main()
