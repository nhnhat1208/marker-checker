from __future__ import annotations

import unittest

from marker_checker_agent.orchestrator import MessageSource
from marker_checker_agent.runtime import MarkerCheckerRuntime


class DummyContext:
    user_id = "@api-user"


class StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def handle_approver_action(
        self,
        *,
        action: str,
        request_id: str,
        actor_name: str | None,
        actor_handle: str,
        note: str,
        source: MessageSource,
    ) -> dict:
        self.calls.append(
            (
                "handle_approver_action",
                {
                    "action": action,
                    "request_id": request_id,
                    "actor_name": actor_name,
                    "actor_handle": actor_handle,
                    "note": note,
                    "source_channel": source.source_channel,
                },
            )
        )
        return {"status": "ok", "request": {"request_id": request_id}}

    def lookup_request(self, request_id: str, actor_handle: str) -> dict:
        self.calls.append(
            ("lookup_request", {"request_id": request_id, "actor_handle": actor_handle})
        )
        return {"status": "ok", "request": {"request_id": request_id}}

    def list_pending_approvals(self, approver_handle: str) -> dict:
        self.calls.append(
            ("list_pending_approvals", {"approver_handle": approver_handle})
        )
        return {"status": "ok", "requests": []}


class RuntimeAliasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = MarkerCheckerRuntime.__new__(MarkerCheckerRuntime)
        self.runtime._orchestrator = StubOrchestrator()

    def test_show_request_alias_maps_to_lookup(self) -> None:
        response = self.runtime.handle_invocation(
            payload={"operation": "show_request", "request_id": "SMK-AAAA1111"},
            context=DummyContext(),
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(
            self.runtime._orchestrator.calls[0],
            (
                "lookup_request",
                {"request_id": "SMK-AAAA1111", "actor_handle": "@api-user"},
            ),
        )

    def test_need_info_alias_maps_to_needinfo(self) -> None:
        response = self.runtime.handle_invocation(
            payload={
                "operation": "need_info",
                "request_id": "SMK-AAAA1111",
                "note": "please add more detail",
            },
            context=DummyContext(),
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(
            self.runtime._orchestrator.calls[0][1]["action"],
            "needinfo",
        )

    def test_my_approvals_alias_maps_to_pending_approvals(self) -> None:
        response = self.runtime.handle_invocation(
            payload={"operation": "my_approvals"},
            context=DummyContext(),
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(
            self.runtime._orchestrator.calls[0],
            ("list_pending_approvals", {"approver_handle": "@api-user"}),
        )


if __name__ == "__main__":
    unittest.main()
