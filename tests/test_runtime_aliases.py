from __future__ import annotations

import unittest
from typing import TYPE_CHECKING

from marker_checker_agent.app import MarkerCheckerApp

if TYPE_CHECKING:
    from marker_checker_agent.domain.models import ActorContext, MessageSource, WorkflowAction


class DummyContext:
    user_id = "@api-user"


class StubOrchestrator:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def handle_approver_action(
        self,
        *,
        actor: ActorContext,
        action: WorkflowAction,
        source: MessageSource,
    ) -> dict:
        self.calls.append(
            (
                "handle_approver_action",
                {
                    "action": action.action.value,
                    "request_id": action.request_id,
                    "actor_name": actor.name,
                    "actor_handle": actor.handle,
                    "note": action.note,
                    "source_channel": source.source_channel,
                },
            )
        )
        return {"status": "ok", "request": {"request_id": action.request_id}}

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
        self.runtime = MarkerCheckerApp.__new__(MarkerCheckerApp)
        self.runtime._orchestrator = StubOrchestrator()  # type: ignore[assignment]

    def test_show_request_alias_maps_to_lookup(self) -> None:
        response = self.runtime.handle_invocation(
            payload={"operation": "show_request", "request_id": "SMK-AAAA1111"},
            context=DummyContext(),  # type: ignore[arg-type]
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(
            self.runtime._orchestrator.calls[0],  # type: ignore[attr-defined]
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
            context=DummyContext(),  # type: ignore[arg-type]
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(
            self.runtime._orchestrator.calls[0][1]["action"],  # type: ignore[attr-defined]
            "needinfo",
        )

    def test_my_approvals_alias_maps_to_pending_approvals(self) -> None:
        response = self.runtime.handle_invocation(
            payload={"operation": "my_approvals"},
            context=DummyContext(),  # type: ignore[arg-type]
        )
        self.assertEqual(response["status"], "ok")
        self.assertEqual(
            self.runtime._orchestrator.calls[0],  # type: ignore[attr-defined]
            ("list_pending_approvals", {"approver_handle": "@api-user"}),
        )


if __name__ == "__main__":
    unittest.main()
