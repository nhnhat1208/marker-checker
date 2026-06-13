from __future__ import annotations

from marker_checker_agent.ai_input_assistance import AssistedParseResult
from marker_checker_agent.orchestrator import AgentOrchestrator
from marker_checker_agent.request_parser import ParsedRequest
from tests.workflow_test_support import WorkflowTestCase


class LlmAssistanceTest(WorkflowTestCase):
    def test_llm_input_assistance_can_build_draft(self) -> None:
        class FakeInputAssistant:
            def assist_request_text(self, text: str) -> AssistedParseResult:
                return AssistedParseResult(
                    parsed_request=ParsedRequest(
                        target_label="sample-object",
                        change_from_summary="disabled",
                        change_to_summary="enabled",
                        approver_handle="@checker",
                    ),
                    parser_name="llm_assisted",
                )

            def generate_clarification_message(
                self,
                *,
                original_message: str,
                missing_fields: list[str],
                validation_errors: list[str],
            ) -> str | None:
                return None

            def generate_confirmation_message(
                self,
                *,
                parsed_request_summary: str,
            ) -> str | None:
                return "Please confirm this request with /confirm."

            def generate_status_summary(self, *, request_summary: str) -> str | None:
                return None

            def generate_history_summary(self, *, request_history: str) -> str | None:
                return None

            def generate_action_result_message(self, *, action_result: str) -> str | None:
                return None

        assisted_orchestrator = AgentOrchestrator(
            request_service=self.request_service,
            audit_service=self.audit_service,
            input_assistant=FakeInputAssistant(),
        )

        draft_response = assisted_orchestrator.handle_requester_message(
            text="please enable sample-object and ask checker to approve it",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(draft_response["status"], "confirmation_required")
        self.assertEqual(draft_response["draft"]["parser"], "llm_assisted")
        self.assertIn("LLM-assisted draft detected", draft_response["message"])

    def test_llm_input_assistance_handle_is_normalized(self) -> None:
        class FakeInputAssistant:
            def assist_request_text(self, text: str) -> AssistedParseResult:
                return AssistedParseResult(
                    parsed_request=ParsedRequest(
                        target_label="sample-object",
                        change_from_summary="disabled",
                        change_to_summary="enabled",
                        approver_handle="@checker",
                    ),
                    parser_name="llm_assisted",
                )

            def generate_clarification_message(
                self,
                *,
                original_message: str,
                missing_fields: list[str],
                validation_errors: list[str],
            ) -> str | None:
                return None

            def generate_confirmation_message(
                self,
                *,
                parsed_request_summary: str,
            ) -> str | None:
                return None

            def generate_status_summary(self, *, request_summary: str) -> str | None:
                return None

            def generate_history_summary(self, *, request_history: str) -> str | None:
                return None

            def generate_action_result_message(self, *, action_result: str) -> str | None:
                return None

        assisted_orchestrator = AgentOrchestrator(
            request_service=self.request_service,
            audit_service=self.audit_service,
            input_assistant=FakeInputAssistant(),
        )

        draft_response = assisted_orchestrator.handle_requester_message(
            text="please enable sample-object and ask checker to approve it",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(draft_response["draft"]["approver_handle"], "@checker")

    def test_llm_input_assistance_metadata_is_returned(self) -> None:
        class FakeInputAssistant:
            def assist_request_text(self, text: str) -> AssistedParseResult:
                return AssistedParseResult(
                    parsed_request=ParsedRequest(
                        target_label="sample-object",
                        change_from_summary="disabled",
                        change_to_summary="enabled",
                        approver_handle="@checker",
                    ),
                    parser_name="llm_assisted",
                    latency_ms=123,
                    model="minimax/minimax-m2.5",
                    prompt_version="request-parse-v1",
                    validation_errors=[],
                )

            def generate_clarification_message(
                self,
                *,
                original_message: str,
                missing_fields: list[str],
                validation_errors: list[str],
            ) -> str | None:
                return None

            def generate_confirmation_message(
                self,
                *,
                parsed_request_summary: str,
            ) -> str | None:
                return None

            def generate_status_summary(self, *, request_summary: str) -> str | None:
                return None

            def generate_history_summary(self, *, request_history: str) -> str | None:
                return None

            def generate_action_result_message(self, *, action_result: str) -> str | None:
                return None

        assisted_orchestrator = AgentOrchestrator(
            request_service=self.request_service,
            audit_service=self.audit_service,
            input_assistant=FakeInputAssistant(),
        )

        draft_response = assisted_orchestrator.handle_requester_message(
            text="please enable sample-object and ask checker to approve it",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(
            draft_response["draft"]["parser_metadata"]["model"],
            "minimax/minimax-m2.5",
        )
        self.assertEqual(
            draft_response["draft"]["parser_metadata"]["prompt_version"],
            "request-parse-v1",
        )
        self.assertEqual(
            draft_response["draft"]["parser_metadata"]["latency_ms"],
            123,
        )

    def test_llm_clarification_message_is_used(self) -> None:
        class FakeInputAssistant:
            def assist_request_text(self, text: str) -> AssistedParseResult:
                return AssistedParseResult(
                    parsed_request=ParsedRequest(
                        target_label="sample-object",
                        change_from_summary="",
                        change_to_summary="",
                        approver_handle="@checker",
                    ),
                    parser_name="llm_assisted",
                    guidance_message="fallback guidance",
                    validation_errors=[],
                )

            def generate_clarification_message(
                self,
                *,
                original_message: str,
                missing_fields: list[str],
                validation_errors: list[str],
            ) -> str | None:
                return "Bạn muốn đổi từ trạng thái nào sang trạng thái nào?"

            def generate_confirmation_message(
                self,
                *,
                parsed_request_summary: str,
            ) -> str | None:
                return None

            def generate_status_summary(self, *, request_summary: str) -> str | None:
                return None

            def generate_history_summary(self, *, request_history: str) -> str | None:
                return None

            def generate_action_result_message(self, *, action_result: str) -> str | None:
                return None

        assisted_orchestrator = AgentOrchestrator(
            request_service=self.request_service,
            audit_service=self.audit_service,
            input_assistant=FakeInputAssistant(),
        )

        response = assisted_orchestrator.handle_requester_message(
            text="please enable sample-object and ask checker to approve it",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        self.assertEqual(response["status"], "missing_fields")
        self.assertEqual(
            response["message"],
            "Bạn muốn đổi từ trạng thái nào sang trạng thái nào?",
        )

    def test_llm_status_and_history_summaries_are_returned(self) -> None:
        class FakeInputAssistant:
            def assist_request_text(self, text: str) -> AssistedParseResult:
                return AssistedParseResult(
                    parsed_request=ParsedRequest(
                        target_label="sample-object",
                        change_from_summary="disabled",
                        change_to_summary="enabled",
                        approver_handle="@checker",
                    ),
                    parser_name="llm_assisted",
                )

            def generate_clarification_message(
                self,
                *,
                original_message: str,
                missing_fields: list[str],
                validation_errors: list[str],
            ) -> str | None:
                return None

            def generate_confirmation_message(
                self,
                *,
                parsed_request_summary: str,
            ) -> str | None:
                return None

            def generate_status_summary(self, *, request_summary: str) -> str | None:
                return "Request is approved for sample-object."

            def generate_history_summary(self, *, request_history: str) -> str | None:
                return "Request was submitted, notified, approved, and later looked up."

            def generate_action_result_message(self, *, action_result: str) -> str | None:
                return "Checker approved the request for sample-object."

        assisted_orchestrator = AgentOrchestrator(
            request_service=self.request_service,
            audit_service=self.audit_service,
            input_assistant=FakeInputAssistant(),
        )

        assisted_orchestrator.handle_requester_message(
            text="please enable sample-object and ask checker to approve it",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        submit_response = assisted_orchestrator.handle_requester_message(
            text="/confirm",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        request_id = submit_response["request"]["request_id"]

        assisted_orchestrator.handle_approver_action(
            action="approve",
            request_id=request_id,
            actor_name="Checker One",
            actor_handle="@checker",
            note="looks good",
            source=self.source,
        )

        lookup_response = assisted_orchestrator.lookup_request(
            request_id=request_id,
            actor_handle="@auditor",
        )
        self.assertEqual(
            lookup_response["summary_message"],
            "Request is approved for sample-object.",
        )

        history_response = assisted_orchestrator.get_history(request_id)
        self.assertEqual(
            history_response["summary_message"],
            "Request was submitted, notified, approved, and later looked up.",
        )

    def test_llm_action_result_message_is_used(self) -> None:
        class FakeInputAssistant:
            def assist_request_text(self, text: str) -> AssistedParseResult:
                return AssistedParseResult(
                    parsed_request=ParsedRequest(
                        target_label="sample-object",
                        change_from_summary="disabled",
                        change_to_summary="enabled",
                        approver_handle="@checker",
                    ),
                    parser_name="llm_assisted",
                )

            def generate_clarification_message(
                self,
                *,
                original_message: str,
                missing_fields: list[str],
                validation_errors: list[str],
            ) -> str | None:
                return None

            def generate_confirmation_message(
                self,
                *,
                parsed_request_summary: str,
            ) -> str | None:
                return None

            def generate_status_summary(self, *, request_summary: str) -> str | None:
                return None

            def generate_history_summary(self, *, request_history: str) -> str | None:
                return None

            def generate_action_result_message(self, *, action_result: str) -> str | None:
                return "Checker approved the request for sample-object."

        assisted_orchestrator = AgentOrchestrator(
            request_service=self.request_service,
            audit_service=self.audit_service,
            input_assistant=FakeInputAssistant(),
        )

        assisted_orchestrator.handle_requester_message(
            text="please enable sample-object and ask checker to approve it",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        submit_response = assisted_orchestrator.handle_requester_message(
            text="/confirm",
            requester_name="Requester One",
            requester_handle="@requester",
            source=self.source,
        )
        request_id = submit_response["request"]["request_id"]

        approve_response = assisted_orchestrator.handle_approver_action(
            action="approve",
            request_id=request_id,
            actor_name="Checker One",
            actor_handle="@checker",
            note="looks good",
            source=self.source,
        )
        self.assertEqual(
            approve_response["message"],
            "Checker approved the request for sample-object.",
        )
