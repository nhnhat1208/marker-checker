from __future__ import annotations

from tests.workflow_test_support import WorkflowTestCase


class RequestFlowTest(WorkflowTestCase):
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
