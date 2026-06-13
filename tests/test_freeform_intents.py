from __future__ import annotations

from tests.workflow_test_support import WorkflowTestCase


class FreeformIntentTest(WorkflowTestCase):
    def test_freeform_lookup_and_history_intents(self) -> None:
        self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
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

        lookup_response = self.orchestrator.handle_requester_message(
            text=f"check {request_id}",
            requester_name="Auditor One",
            requester_handle="@auditor",
            source=self.source,
        )
        self.assertEqual(lookup_response["status"], "ok")
        self.assertEqual(lookup_response["request"]["request_id"], request_id)

        history_response = self.orchestrator.handle_requester_message(
            text=f"history {request_id}",
            requester_name="Auditor One",
            requester_handle="@auditor",
            source=self.source,
        )
        self.assertEqual(history_response["status"], "ok")
        self.assertGreaterEqual(len(history_response["timeline"]), 2)

    def test_freeform_cancel_intent(self) -> None:
        self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
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

        cancel_response = self.orchestrator.handle_requester_message(
            text=f"cancel {request_id} no longer needed",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(cancel_response["status"], "ok")
        self.assertEqual(cancel_response["request"]["review_status"], "cancelled")

    def test_freeform_resubmit_intent(self) -> None:
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

        self.orchestrator.handle_approver_action(
            action="needinfo",
            request_id=request_id,
            actor_name="Checker One",
            actor_handle="@checker",
            note="please update the target state",
            source=self.source,
        )

        resubmit_response = self.orchestrator.handle_requester_message(
            text=(
                f"resubmit {request_id} for sample-object, change from old-state "
                "to new-state-v2, ask @checker to approve"
            ),
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(resubmit_response["status"], "ok")
        self.assertEqual(resubmit_response["request"]["review_status"], "submitted")
        self.assertEqual(resubmit_response["request"]["last_submitted_revision"], 2)

    def test_pending_request_lists(self) -> None:
        self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
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

        my_pending_response = self.orchestrator.handle_requester_message(
            text="my pending requests",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(my_pending_response["status"], "ok")
        self.assertEqual(len(my_pending_response["requests"]), 1)
        self.assertEqual(my_pending_response["requests"][0]["request_id"], request_id)

        approvals_response = self.orchestrator.handle_requester_message(
            text="what needs approval",
            requester_name="Checker One",
            requester_handle="@checker",
            source=self.source,
        )
        self.assertEqual(approvals_response["status"], "ok")
        self.assertEqual(len(approvals_response["requests"]), 1)
        self.assertEqual(approvals_response["requests"][0]["request_id"], request_id)

        my_approvals_response = self.orchestrator.handle_requester_message(
            text="my approvals",
            requester_name="Checker One",
            requester_handle="@checker",
            source=self.source,
        )
        self.assertEqual(my_approvals_response["status"], "ok")
        self.assertEqual(len(my_approvals_response["requests"]), 1)
        self.assertEqual(my_approvals_response["requests"][0]["request_id"], request_id)

    def test_show_request_and_needinfo_freeform_intents(self) -> None:
        self.orchestrator.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
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

        show_response = self.orchestrator.handle_requester_message(
            text=f"show request {request_id}",
            requester_name="Auditor One",
            requester_handle="@auditor",
            source=self.source,
        )
        self.assertEqual(show_response["status"], "ok")
        self.assertEqual(show_response["request"]["request_id"], request_id)

        needinfo_response = self.orchestrator.handle_requester_message(
            text=f"need info {request_id} please share rollout reason",
            requester_name="Checker One",
            requester_handle="@checker",
            source=self.source,
        )
        self.assertEqual(needinfo_response["status"], "ok")
        self.assertEqual(needinfo_response["request"]["review_status"], "needs_info")
