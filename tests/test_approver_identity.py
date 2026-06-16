from __future__ import annotations

import unittest

from agent.parsing.request_parser import parse_request_text
from agent.web.notifier import WebNotificationHub


class ApproverIdentityTest(unittest.TestCase):
    def test_parse_request_text_accepts_email_approver(self) -> None:
        parsed = parse_request_text(
            "for api-gateway, change from disabled to enabled, ask Annie@example.COM to approve"
        )

        assert parsed is not None
        self.assertEqual(parsed.target_label, "api-gateway")
        self.assertEqual(parsed.change_from_summary, "disabled")
        self.assertEqual(parsed.change_to_summary, "enabled")
        self.assertEqual(parsed.approver_handle, "annie@example.com")

    def test_parse_request_text_accepts_review_wording(self) -> None:
        parsed = parse_request_text(
            "change from timeout: 30s to timeout: 60s, ops@example.com should review"
        )

        assert parsed is not None
        self.assertEqual(parsed.approver_handle, "ops@example.com")

    def test_parse_request_text_does_not_match_vietnamese_wording(self) -> None:
        parsed = parse_request_text(
            "tắt api-gateway, nhờ annie@example.com duyệt"
        )

        self.assertIsNone(parsed)

    def test_web_notifier_routes_email_case_insensitively(self) -> None:
        hub = WebNotificationHub()

        captured: list[object] = []
        hub._broadcast = lambda user_email, response: captured.append((user_email, response))  # type: ignore[method-assign]

        hub.notify_requester("Requester@Example.com", "Approved")

        self.assertEqual(captured[0][0], "requester@example.com")


if __name__ == "__main__":
    unittest.main()
