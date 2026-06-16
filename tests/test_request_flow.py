from __future__ import annotations

from agent.domain.enums import Operation
from agent.domain.models import ActorContext, MessageSource, WorkflowAction
from tests.workflow_test_support import WorkflowTestCase


class RequestFlowTest(WorkflowTestCase):
    def test_draft_ui_response_and_bare_confirm_discard(self) -> None:
        draft_response = self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(draft_response["status"], "confirmation_required")
        self.assertEqual(draft_response["ui_response"]["kind"], "confirmation_required")
        self.assertEqual(draft_response["ui_response"]["draft"]["approver_handle"], "@checker")

        discard_response = self.orchestrator.handle_requester_message(
            text="discard",
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(discard_response["status"], "ok")

        self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        confirm_response = self.orchestrator.handle_requester_message(
            text="confirm",
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(confirm_response["status"], "submitted")

    def test_submit_approve_lookup_and_history(self) -> None:
        draft_response = self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(draft_response["status"], "confirmation_required")

        submit_response = self.orchestrator.handle_requester_message(
            text="/confirm",
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(submit_response["status"], "submitted")
        request_id = submit_response["request"]["request_id"]
        self.assertTrue(request_id.startswith("SMK-"))
        self.assertEqual(len(self.notifications), 1)

        approve_response = self.orchestrator.handle_approver_action(
            actor=ActorContext(name="Checker One", handle="@checker"),
            action=WorkflowAction(action=Operation.APPROVE, request_id=request_id, note="looks good"),
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
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        submit_response = self.orchestrator.handle_requester_message(
            text="/confirm",
            requester=ActorContext(name="Requester One", handle="@requester"),
            source=self.source,
        )
        request_id = submit_response["request"]["request_id"]

        needinfo_response = self.orchestrator.handle_approver_action(
            actor=ActorContext(name="Checker One", handle="@checker"),
            action=WorkflowAction(
                action=Operation.NEEDINFO, request_id=request_id, note="please clarify target state"
            ),
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
            actor=ActorContext(name="Requester One", handle="@requester"),
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

    def test_web_request_can_route_to_email_approver(self) -> None:
        web_source = MessageSource(
            source_channel="web",
            channel_id="requester@example.com",
            thread_id="requester@example.com",
        )
        requester = ActorContext(name="Requester One", handle="requester@example.com")

        draft_response = self.orchestrator.handle_requester_message(
            text="for api-gateway, change from disabled to enabled, ask Annie@example.com to approve",
            requester=requester,
            source=web_source,
        )
        self.assertEqual(draft_response["status"], "confirmation_required")
        self.assertEqual(draft_response["draft"]["approver_handle"], "annie@example.com")

        submit_response = self.orchestrator.handle_requester_message(
            text="/confirm",
            requester=requester,
            source=web_source,
        )
        self.assertEqual(submit_response["status"], "submitted")
        self.assertEqual(submit_response["request"]["approver_handle"], "annie@example.com")

        record = self.request_service.get_request(submit_response["request"]["request_id"])
        self.assertEqual(record.origin_channel_id, "requester@example.com")
        self.assertEqual(record.approver_handle, "annie@example.com")

    def test_web_self_approval_does_not_emit_requester_notification(self) -> None:
        requester_notifications: list[tuple[str, str]] = []
        self.orchestrator.set_requester_notification_callback(
            lambda channel_id, message: requester_notifications.append((channel_id, message))
        )

        web_source = MessageSource(
            source_channel="web",
            channel_id="requester@example.com",
            thread_id="requester@example.com",
        )
        requester = ActorContext(name="Requester One", handle="requester@example.com")

        self.orchestrator.handle_requester_message(
            text="for api-gateway, change from disabled to enabled, ask requester@example.com to approve",
            requester=requester,
            source=web_source,
        )
        submit_response = self.orchestrator.handle_requester_message(
            text="/confirm",
            requester=requester,
            source=web_source,
        )

        approve_response = self.orchestrator.handle_approver_action(
            actor=requester,
            action=WorkflowAction(
                action=Operation.APPROVE,
                request_id=submit_response["request"]["request_id"],
                note="looks good",
            ),
            source=web_source,
        )
        self.assertEqual(approve_response["status"], "ok")
        self.assertEqual(requester_notifications, [])
