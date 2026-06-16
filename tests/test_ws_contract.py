from __future__ import annotations

import unittest

from agent.contracts.ws import (
    UiRequestSummary,
    UiResponse,
    WsDoneMessage,
    WsStructuredMessage,
    dump_ws_server_message,
    parse_ws_client_message,
)
from agent.web.ws_messages import build_request_ui_response, done_payload


class WsContractTest(unittest.TestCase):
    def test_parse_structured_message_contract(self) -> None:
        message = parse_ws_client_message(
            {
                "type": "structured_message",
                "draft": {
                    "mode": "config_change",
                    "request_format": "text",
                    "request": "change nginx timeout",
                    "approver": "@ops",
                    "before": {
                        "enabled": True,
                        "format": "yaml",
                        "value": "timeout: 30s\n",
                    },
                    "after": {
                        "enabled": True,
                        "format": "yaml",
                        "value": "timeout: 60s\n",
                    },
                },
            }
        )

        self.assertIsInstance(message, WsStructuredMessage)
        assert isinstance(message, WsStructuredMessage)
        self.assertEqual(message.draft.before.format, "yaml")
        self.assertEqual(message.draft.after.value, "timeout: 60s\n")

    def test_dump_server_message_excludes_none(self) -> None:
        payload = dump_ws_server_message(
            WsDoneMessage(
                type="done",
                response={"status": "ok"},
                ui_response=UiResponse(
                    kind="request_status",
                    impact_note="LLM impact note",
                    request=UiRequestSummary(
                        request_id="REQ-123",
                        requester_handle="@alice",
                        approver_handle="@ops",
                        target_label="nginx-config",
                        change_from_summary="30s",
                        change_to_summary="60s",
                        review_status="submitted",
                        request_text="change timeout",
                        structured_payload=None,
                    ),
                ),
            )
        )

        self.assertEqual(payload["type"], "done")
        self.assertIn("ui_response", payload)
        self.assertNotIn("title", payload["ui_response"])
        self.assertEqual(payload["ui_response"]["request"]["request_id"], "REQ-123")
        self.assertEqual(payload["ui_response"]["impact_note"], "LLM impact note")

    def test_build_request_ui_response_copies_impact_note_to_request(self) -> None:
        response = build_request_ui_response(
            {
                "request_id": "REQ-123",
                "requester_handle": "@alice",
                "approver_handle": "@ops",
                "target_label": "nginx-config",
                "change_from_summary": "30s",
                "change_to_summary": "60s",
                "review_status": "submitted",
                "request_text": "change timeout",
            },
            impact_note="Increase timeout before traffic spike.",
        )

        assert response.request is not None
        self.assertEqual(response.impact_note, "Increase timeout before traffic spike.")
        self.assertEqual(response.request.impact_note, "Increase timeout before traffic spike.")

    def test_missing_fields_response_becomes_ui_response(self) -> None:
        payload = dump_ws_server_message(
            done_payload(
                {
                    "status": "missing_fields",
                    "message": "Who should approve this deployment?",
                    "missing_fields": ["approver_handle", "target_label"],
                }
            )
        )

        self.assertEqual(payload["type"], "done")
        self.assertEqual(payload["ui_response"]["kind"], "missing_fields")
        self.assertEqual(payload["ui_response"]["missing_fields"], ["approver_handle", "target_label"])
        self.assertEqual(payload["ui_response"]["guidance_message"], "Who should approve this deployment?")

    def test_missing_fields_response_preserves_partial_draft(self) -> None:
        payload = dump_ws_server_message(
            done_payload(
                {
                    "status": "missing_fields",
                    "message": "Please fill the missing fields.",
                    "missing_fields": ["approver_handle"],
                    "draft": {
                        "requester_handle": "alice@example.com",
                        "approver_handle": "",
                        "target_label": "api-gateway",
                        "change_from_summary": "disabled",
                        "change_to_summary": "enabled",
                        "parser": "llm_assisted",
                    },
                }
            )
        )

        self.assertEqual(payload["ui_response"]["kind"], "missing_fields")
        self.assertEqual(payload["ui_response"]["draft"]["target_label"], "api-gateway")
        self.assertEqual(payload["ui_response"]["draft"]["change_from_summary"], "disabled")
        self.assertEqual(payload["ui_response"]["draft"]["change_to_summary"], "enabled")

    def test_ws_contract_declares_all_message_types(self) -> None:
        from agent.contracts.ws import WS_CONTRACT

        self.assertEqual(len(WS_CONTRACT.client_messages), 3)
        self.assertEqual(len(WS_CONTRACT.server_messages), 3)
        self.assertIn(WsStructuredMessage, WS_CONTRACT.client_messages)
        self.assertIn(WsDoneMessage, WS_CONTRACT.server_messages)


if __name__ == "__main__":
    unittest.main()
