"""
Tests for intent routing: regex fast-path and LLM-assisted classification.

Coverage:
- Tight REQUEST_ID_PATTERN (requires digit in last segment)
- Vietnamese natural language routed via fake LLM classify_intent
- unknown operation → NEEDS_INPUT without calling assist_request_text
- new_request → assist_request_text is called
"""
from __future__ import annotations

from marker_checker_agent.ai.intent_types import (
    AssistedParseResult,
    IntentManagement,
    IntentNewRequest,
    IntentUnknown,
)
from marker_checker_agent.domain.enums import Operation
from marker_checker_agent.domain.models import ActorContext
from marker_checker_agent.parsing.intent_router import FreeformIntentRouter
from marker_checker_agent.parsing.request_parser import ParsedRequest
from marker_checker_agent.request_coordinator import RequestCoordinator
from tests.workflow_test_support import WorkflowTestCase

# ---------------------------------------------------------------------------
# Regex router unit tests (no orchestrator, no LLM)
# ---------------------------------------------------------------------------

class IntentRouterPatternTest(WorkflowTestCase):
    def setUp(self) -> None:
        super().setUp()
        self.router = FreeformIntentRouter()

    def _route(self, text: str):
        return self.router.route(text)

    # --- REQUEST_ID_PATTERN: must have digit in last segment ---

    def test_real_request_id_is_routed(self) -> None:
        # hex suffix always has digits in practice
        result = self._route("check SMK-A3F2C891")
        self.assertIsNotNone(result)
        self.assertEqual(result.operation, Operation.LOOKUP)
        self.assertEqual(result.request_id, "SMK-A3F2C891")

    def test_numeric_only_suffix_is_routed(self) -> None:
        result = self._route("status SMK-001")
        self.assertIsNotNone(result)
        self.assertEqual(result.operation, Operation.LOOKUP)

    def test_hyphenated_word_without_digit_not_routed(self) -> None:
        # "api-gateway" has no digit → must NOT match LOOKUP
        self.assertIsNone(self._route("check api-gateway"))
        self.assertIsNone(self._route("cancel nginx-config"))
        self.assertIsNone(self._route("status dark-mode"))

    def test_cancel_with_note(self) -> None:
        result = self._route("cancel SMK-1A2B3C4D no longer needed")
        self.assertIsNotNone(result)
        self.assertEqual(result.operation, Operation.CANCEL)
        self.assertEqual(result.note, "no longer needed")

    def test_history_routed(self) -> None:
        result = self._route("history SMK-ABC-456")
        self.assertIsNotNone(result)
        self.assertEqual(result.operation, Operation.HISTORY)

    # --- MY_PENDING English regex ---

    def test_list_requests_routed(self) -> None:
        for text in (
            "list requests", "list my requests", "show requests",
            "my pending requests", "my requests",
        ):
            with self.subTest(text=text):
                result = self._route(text)
                self.assertIsNotNone(result)
                self.assertEqual(result.operation, Operation.MY_PENDING)

    def test_pending_approvals_routed(self) -> None:
        for text in ("pending approvals", "my approvals", "what needs approval"):
            with self.subTest(text=text):
                result = self._route(text)
                self.assertIsNotNone(result)
                self.assertEqual(result.operation, Operation.PENDING_APPROVALS)

    # --- Vietnamese falls through regex (no match) ---

    def test_vietnamese_management_not_caught_by_regex(self) -> None:
        # These should all return None so LLM handles them
        for text in (
            "list các request được tạo",
            "danh sách request",
            "hủy SMK-001",
            "xem SMK-001",
            "các request chờ duyệt",
        ):
            with self.subTest(text=text):
                self.assertIsNone(self._route(text), msg=f"Expected no regex match for {text!r}")


# ---------------------------------------------------------------------------
# Orchestrator + fake LLM: classify_intent scenarios
# ---------------------------------------------------------------------------

class _FakeAssistantBase:
    """Minimal fake — subclasses override only what they need."""

    classify_called_with: list[str]
    assist_called_with: list[str]

    def __init__(self) -> None:
        self.classify_called_with = []
        self.assist_called_with = []

    def classify_intent(self, text: str) -> IntentUnknown:
        self.classify_called_with.append(text)
        return IntentUnknown()

    def assist_request_text(self, text: str) -> AssistedParseResult:
        self.assist_called_with.append(text)
        return AssistedParseResult(parsed_request=None, parser_name="llm_assisted")

    def generate_clarification_message(
        self, *, original_message, missing_fields, validation_errors
    ) -> str | None:
        return None

    def generate_confirmation_message(self, *, parsed_request_summary) -> str | None:
        return None

    def generate_status_summary(self, *, request_summary) -> str | None:
        return None

    def generate_history_summary(self, *, request_history) -> str | None:
        return None

    def generate_action_result_message(self, *, action_result) -> str | None:
        return None


class LlmIntentRoutingTest(WorkflowTestCase):

    def _make_orchestrator(self, assistant) -> RequestCoordinator:
        orc = RequestCoordinator(
            request_service=self.request_service,
            audit_service=self.audit_service,
            input_assistant=assistant,
        )
        orc.set_approver_notification_callback(self.notifications.append)
        return orc

    def _submit_request(self, orc: RequestCoordinator) -> str:
        orc.handle_requester_message(
            text="for sample-object, change from disabled to enabled, ask @checker to approve",
            requester=ActorContext(name="Requester", handle="@requester"),
            source=self.source,
        )
        resp = orc.handle_requester_message(
            text="/confirm",
            requester=ActorContext(name="Requester", handle="@requester"),
            source=self.source,
        )
        return resp["request"]["request_id"]

    # --- unknown → NEEDS_INPUT, assist_request_text never called ---

    def test_unknown_intent_returns_needs_input(self) -> None:
        class Fake(_FakeAssistantBase):
            def classify_intent(self, text):
                self.classify_called_with.append(text)
                return IntentUnknown()

        fake = Fake()
        orc = self._make_orchestrator(fake)
        resp = orc.handle_requester_message(
            text="gibberish that makes no sense",
            requester=ActorContext(name="User", handle="@user"),
            source=self.source,
        )
        self.assertEqual(resp["status"], "needs_input")
        self.assertEqual(fake.assist_called_with, [], "assist_request_text must NOT be called for unknown")

    # --- LLM routes Vietnamese → my_pending ---

    def test_llm_routes_vietnamese_my_pending(self) -> None:
        class Fake(_FakeAssistantBase):
            def classify_intent(self, text):
                self.classify_called_with.append(text)
                return IntentManagement(operation=Operation.MY_PENDING)

        fake = Fake()
        orc = self._make_orchestrator(fake)
        request_id = self._submit_request(orc)

        resp = orc.handle_requester_message(
            text="list các request được tạo",
            requester=ActorContext(name="Requester", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(len(resp["requests"]), 1)
        self.assertEqual(resp["requests"][0]["request_id"], request_id)
        self.assertEqual(fake.assist_called_with, [], "assist_request_text must NOT be called for my_pending")

    # --- LLM routes Vietnamese → pending_approvals ---

    def test_llm_routes_vietnamese_pending_approvals(self) -> None:
        class Fake(_FakeAssistantBase):
            def classify_intent(self, text):
                self.classify_called_with.append(text)
                return IntentManagement(operation=Operation.PENDING_APPROVALS)

        fake = Fake()
        orc = self._make_orchestrator(fake)
        request_id = self._submit_request(orc)

        resp = orc.handle_requester_message(
            text="các request chờ tôi duyệt",
            requester=ActorContext(name="Checker", handle="@checker"),
            source=self.source,
        )
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(len(resp["requests"]), 1)
        self.assertEqual(resp["requests"][0]["request_id"], request_id)

    # --- LLM routes Vietnamese → cancel with request_id ---

    def test_llm_routes_vietnamese_cancel(self) -> None:
        class Fake(_FakeAssistantBase):
            _target_id: str = ""

            def classify_intent(self, text):
                self.classify_called_with.append(text)
                return IntentManagement(
                    operation=Operation.CANCEL,
                    request_id=self._target_id,
                    note="không cần nữa",
                )

        fake = Fake()
        orc = self._make_orchestrator(fake)
        request_id = self._submit_request(orc)
        fake._target_id = request_id

        resp = orc.handle_requester_message(
            text=f"hủy {request_id} không cần nữa",
            requester=ActorContext(name="Requester", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(resp["status"], "ok")
        self.assertEqual(resp["request"]["review_status"], "cancelled")

    # --- new_request → assist_request_text IS called ---

    def test_new_request_calls_assist_request_text(self) -> None:
        class Fake(_FakeAssistantBase):
            def classify_intent(self, text):
                self.classify_called_with.append(text)
                return IntentNewRequest()  # empty fields → falls through to assist_request_text

            def assist_request_text(self, text):
                self.assist_called_with.append(text)
                return AssistedParseResult(
                    parsed_request=ParsedRequest(
                        target_label="api-gateway",
                        change_from_summary="disabled",
                        change_to_summary="enabled",
                        approver_handle="@checker",
                    ),
                    parser_name="llm_assisted",
                )

        fake = Fake()
        orc = self._make_orchestrator(fake)
        resp = orc.handle_requester_message(
            text="tắt api-gateway, nhờ @checker duyệt",
            requester=ActorContext(name="Requester", handle="@requester"),
            source=self.source,
        )
        self.assertEqual(resp["status"], "confirmation_required")
        self.assertEqual(len(fake.assist_called_with), 1)
        self.assertEqual(resp["draft"]["target_label"], "api-gateway")
