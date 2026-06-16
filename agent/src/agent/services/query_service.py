from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from agent.domain.enums import ActorKind, AuditEventType, ResponseStatus
from agent.domain.models import (
    ActorContext,
    AuditEventInput,
    CoordinatorResponse,
    TimelineEvent,
    UiResponse,
)
from agent.services.request_service import RequestNotFoundError

if TYPE_CHECKING:
    from agent.ai.assistant import RequestInputAssistant
    from agent.domain.models import RequestSummary
    from agent.services.audit_service import AuditService
    from agent.services.request_service import RequestService

LOGGER = logging.getLogger(__name__)


class RequestQueryService:
    """Read-only operations: lookup, history, search, and list requests."""

    def __init__(
        self,
        *,
        request_service: RequestService,
        audit_service: AuditService,
        input_assistant: RequestInputAssistant | None = None,
    ) -> None:
        self._request_service = request_service
        self._audit_service = audit_service
        self._input_assistant = input_assistant

    def lookup_request(self, request_id: str, actor_handle: str) -> CoordinatorResponse:
        try:
            request = self._request_service.get_request_summary(request_id)
            request = _request_summary_copy(
                request,
                impact_note=_estimate_impact_note(self._input_assistant, request),
            )
        except RequestNotFoundError as exc:
            return {"status": ResponseStatus.ERROR, "message": str(exc)}

        self._audit_service.record_event(
            request_id=request_id,
            actor=ActorContext(handle=actor_handle),
            event=AuditEventInput(
                event_type=AuditEventType.LOOKUP_PERFORMED,
                actor_kind=ActorKind.LOOKUP_USER,
                summary="Request lookup performed",
                event_payload={"request_id": request_id},
            ),
        )
        return {
            "status": ResponseStatus.OK,
            "request": request,
            "summary_message": _generate_request_status_summary(self._input_assistant, request),
            "ui_response": _request_ui_response(request),
        }

    def get_history(self, request_id: str) -> CoordinatorResponse:
        timeline = self._audit_service.list_timeline(request_id)
        history_payload: list[TimelineEvent] = [
            {
                "event_sequence": event.event_sequence,
                "event_type": event.event_type,
                "summary": event.summary,
                "actor_handle": event.actor_handle,
                "occurred_at": event.occurred_at.isoformat(),
            }
            for event in timeline
        ]
        return {
            "status": ResponseStatus.OK,
            "timeline": history_payload,
            "summary_message": _generate_request_history_summary(self._input_assistant, history_payload),
        }

    def search_by_target(self, target_name: str) -> CoordinatorResponse:
        if not target_name:
            return {"status": ResponseStatus.ERROR, "message": "No target name provided."}
        requests = _with_impact_notes(
            self._input_assistant,
            self._request_service.search_by_target_label(target_name),
        )
        return {
            "status": ResponseStatus.OK,
            "message": _format_request_list(
                requests,
                empty_message=f"No requests found for target '{target_name}'.",
                title=f"Requests for '{target_name}':",
            ),
            "requests": requests,
            "ui_response": _request_list_ui_response(requests, title=f"Requests for '{target_name}'"),
        }

    def list_requester_pending(self, requester_handle: str) -> CoordinatorResponse:
        requests = _with_impact_notes(
            self._input_assistant,
            self._request_service.list_requester_pending_summaries(requester_handle),
        )
        return {
            "status": ResponseStatus.OK,
            "message": _format_request_list(
                requests,
                empty_message="You have no active requests.",
                title="Your active requests:",
            ),
            "requests": requests,
            "ui_response": _request_list_ui_response(requests, title="Your active requests"),
        }

    def list_pending_approvals(self, approver_handle: str) -> CoordinatorResponse:
        requests = _with_impact_notes(
            self._input_assistant,
            self._request_service.list_approver_pending_summaries(approver_handle),
        )
        return {
            "status": ResponseStatus.OK,
            "message": _format_request_list(
                requests,
                empty_message="You have no requests waiting for approval.",
                title="Requests waiting for your approval:",
            ),
            "requests": requests,
            "ui_response": _request_list_ui_response(requests, title="Requests waiting for your approval"),
        }


def _generate_request_status_summary(
    assistant: RequestInputAssistant | None,
    request: RequestSummary,
) -> str | None:
    if not assistant:
        return None
    summary = (
        f"request_id: {request['request_id']}\n"
        f"status: {request['review_status']}\n"
        f"target: {request['target_label']}\n"
        f"from: {request['change_from_summary']}\n"
        f"to: {request['change_to_summary']}\n"
        f"requester: {request['requester_handle']}\n"
        f"approver: {request['approver_handle']}\n"
        f"revision: {request['last_submitted_revision']}"
    )
    return assistant.generate_status_summary(request_summary=summary)


def _generate_request_history_summary(
    assistant: RequestInputAssistant | None,
    history_payload: list[TimelineEvent],
) -> str | None:
    if not assistant or not history_payload:
        return None
    history_lines = [
        (
            f"{event['event_sequence']}. {event['event_type']} | "
            f"{event['summary']} | actor={event['actor_handle']} | "
            f"at={event['occurred_at']}"
        )
        for event in history_payload
    ]
    return assistant.generate_history_summary(request_history="\n".join(history_lines))


def _format_request_list(
    requests: list[RequestSummary],
    *,
    empty_message: str,
    title: str,
) -> str:
    if not requests:
        return empty_message
    lines = [title]
    lines.extend(
        f"- {req.get('request_id')} | {req.get('review_status')} | "
        f"{req.get('target_label')} | "
        f"{req.get('change_from_summary')} -> {req.get('change_to_summary')}"
        for req in requests[:5]
    )
    if len(requests) > 5:
        lines.append(f"... and {len(requests) - 5} more.")
    return "\n".join(lines)


def _request_ui_response(request: RequestSummary) -> UiResponse:
    request_id = request.get("request_id", "Request")
    status = request.get("review_status", "").replace("_", " ")
    target = request.get("target_label", "")
    approver = request.get("approver_handle", "")

    body_parts: list[str] = []
    if status:
        body_parts.append(f"Status: {status}")
    if target:
        body_parts.append(f"Target: {target}")
    if approver:
        body_parts.append(f"Approver: {approver}")

    return {
        "kind": "request_status",
        "status": request.get("review_status", ""),
        "title": f"Request {request_id}",
        "body": " · ".join(body_parts) if body_parts else None,
        "request": request,
    }


def _request_summary_copy(request: RequestSummary, *, impact_note: str | None) -> RequestSummary:
    copied = dict(request)
    if impact_note and not str(copied.get("impact_note", "")).strip():
        copied["impact_note"] = impact_note
    return copied


def _estimate_impact_note(
    assistant: RequestInputAssistant | None,
    request: RequestSummary,
) -> str | None:
    if not assistant:
        return None
    existing = str(request.get("impact_note", "")).strip()
    if existing:
        return existing
    if (
        not request.get("target_label")
        and not request.get("change_from_summary")
        and not request.get("change_to_summary")
    ):
        return None
    return assistant.generate_impact_note(
        target_label=request.get("target_label", ""),
        change_from=request.get("change_from_summary", ""),
        change_to=request.get("change_to_summary", ""),
    )


def _with_impact_notes(
    assistant: RequestInputAssistant | None,
    requests: list[RequestSummary],
) -> list[RequestSummary]:
    if not assistant:
        return requests
    return [
        _request_summary_copy(
            request,
            impact_note=_estimate_impact_note(assistant, request),
        )
        for request in requests
    ]


def _request_list_ui_response(requests: list[RequestSummary], *, title: str) -> UiResponse:
    return {
        "kind": "request_list",
        "title": title,
        "requests": requests,
        "status": ResponseStatus.OK,
    }
