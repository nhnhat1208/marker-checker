from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from marker_checker_agent.domain.enums import AuditEventType
from marker_checker_agent.request_parser import (
    ParsedRequest,
    format_confirmation_message,
    list_missing_required_fields,
    parse_request_text,
)
from marker_checker_agent.services.audit_service import AuditService
from marker_checker_agent.services.request_service import (
    InvalidTransitionError,
    RequestNotFoundError,
    RequestService,
)


@dataclass
class MessageSource:
    source_channel: str = "telegram"
    channel_id: str | None = None
    thread_id: str | None = None
    source_message_id: str | None = None


@dataclass
class PendingDraft:
    request_text: str
    requester_name: str | None
    parsed_request: ParsedRequest
    business_reason: str | None
    source: MessageSource


class AgentOrchestrator:
    def __init__(self, *, request_service: RequestService, audit_service: AuditService) -> None:
        self._request_service = request_service
        self._audit_service = audit_service
        self._pending_drafts: dict[str, PendingDraft] = {}
        self._draft_lock = threading.Lock()
        self._notify_approver: Callable[[dict[str, Any]], None] | None = None

    def set_approver_notification_callback(
        self, callback: Callable[[dict[str, Any]], None]
    ) -> None:
        self._notify_approver = callback

    def handle_requester_message(
        self,
        *,
        text: str,
        requester_name: str | None,
        requester_handle: str,
        source: MessageSource,
    ) -> dict[str, Any]:
        normalized = text.strip()

        if normalized.lower() == "/confirm":
            return self._confirm_pending_draft(
                requester_name=requester_name,
                requester_handle=requester_handle,
            )

        parsed = parse_request_text(normalized)
        if not parsed:
            return {
                "status": "needs_input",
                "message": (
                    "Use a message like: "
                    "'for target-name, change from old-value to new-value, "
                    "ask @approver to approve'."
                ),
            }

        missing_fields = list_missing_required_fields(parsed)
        if missing_fields:
            return {
                "status": "missing_fields",
                "message": f"Missing fields: {', '.join(missing_fields)}",
            }

        draft = PendingDraft(
            request_text=normalized,
            requester_name=requester_name,
            parsed_request=parsed,
            business_reason=None,
            source=source,
        )
        with self._draft_lock:
            self._pending_drafts[requester_handle] = draft

        return {
            "status": "confirmation_required",
            "message": format_confirmation_message(draft.parsed_request),
            "draft": {
                "requester_handle": requester_handle,
                "approver_handle": draft.parsed_request.approver_handle,
                "target_label": draft.parsed_request.target_label,
                "change_from_summary": draft.parsed_request.change_from_summary,
                "change_to_summary": draft.parsed_request.change_to_summary,
            },
        }

    def handle_approver_action(
        self,
        *,
        action: str,
        request_id: str,
        actor_name: str | None,
        actor_handle: str,
        note: str,
        source: MessageSource,
    ) -> dict[str, Any]:
        try:
            if action == "approve":
                record = self._request_service.approve_request(
                    request_id=request_id,
                    actor_name=actor_name,
                    actor_handle=actor_handle,
                    note=note,
                    source_channel=source.source_channel,
                    source_message_id=source.source_message_id,
                )
            elif action == "reject":
                record = self._request_service.reject_request(
                    request_id=request_id,
                    actor_name=actor_name,
                    actor_handle=actor_handle,
                    reason=note,
                    source_channel=source.source_channel,
                    source_message_id=source.source_message_id,
                )
            elif action == "needinfo":
                record = self._request_service.request_more_info(
                    request_id=request_id,
                    actor_name=actor_name,
                    actor_handle=actor_handle,
                    note=note,
                    source_channel=source.source_channel,
                    source_message_id=source.source_message_id,
                )
            elif action == "cancel":
                record = self._request_service.cancel_request(
                    request_id=request_id,
                    actor_name=actor_name,
                    actor_handle=actor_handle,
                    note=note,
                    source_channel=source.source_channel,
                    source_message_id=source.source_message_id,
                )
            else:
                return {"status": "error", "message": f"Unsupported action: {action}"}
        except (InvalidTransitionError, RequestNotFoundError, ValueError) as exc:
            return {"status": "error", "message": str(exc)}

        return {
            "status": "ok",
            "message": f"{record.request_id} moved to {record.review_status}.",
            "request": self._request_service.get_request_summary(record.request_id),
        }

    def handle_resubmission(
        self,
        *,
        request_id: str,
        text: str,
        actor_name: str | None,
        actor_handle: str,
        source: MessageSource,
    ) -> dict[str, Any]:
        parsed = parse_request_text(text)
        if not parsed:
            return {"status": "error", "message": "Could not parse resubmission message."}

        try:
            record = self._request_service.resubmit_request(
                request_id=request_id,
                actor_name=actor_name,
                actor_handle=actor_handle,
                target_label=parsed.target_label,
                change_from_summary=parsed.change_from_summary,
                change_to_summary=parsed.change_to_summary,
                business_reason=None,
                request_text=text,
                source_channel=source.source_channel,
                source_message_id=source.source_message_id,
            )
        except (InvalidTransitionError, RequestNotFoundError) as exc:
            return {"status": "error", "message": str(exc)}

        return {
            "status": "ok",
            "message": f"{record.request_id} resubmitted as revision {record.last_submitted_revision}.",
            "request": self._request_service.get_request_summary(record.request_id),
        }

    def lookup_request(self, request_id: str, actor_handle: str) -> dict[str, Any]:
        try:
            request = self._request_service.get_request_summary(request_id)
        except RequestNotFoundError as exc:
            return {"status": "error", "message": str(exc)}

        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.LOOKUP_PERFORMED,
            actor_handle=actor_handle,
            actor_kind="lookup_user",
            summary="Request lookup performed",
            event_payload={"request_id": request_id},
        )
        return {"status": "ok", "request": request}

    def get_history(self, request_id: str) -> dict[str, Any]:
        timeline = self._audit_service.list_timeline(request_id)
        return {
            "status": "ok",
            "timeline": [
                {
                    "event_sequence": event.event_sequence,
                    "event_type": event.event_type,
                    "summary": event.summary,
                    "actor_handle": event.actor_handle,
                    "occurred_at": event.occurred_at.isoformat(),
                }
                for event in timeline
            ],
        }

    def _confirm_pending_draft(
        self,
        *,
        requester_name: str | None,
        requester_handle: str,
    ) -> dict[str, Any]:
        with self._draft_lock:
            draft = self._pending_drafts.pop(requester_handle, None)

        if draft is None:
            return {
                "status": "error",
                "message": "No pending draft found. Send a request message first.",
            }

        record = self._request_service.create_request(
            request_text=draft.request_text,
            requester_name=requester_name,
            requester_handle=requester_handle,
            approver_name=None,
            approver_handle=draft.parsed_request.approver_handle,
            target_label=draft.parsed_request.target_label,
            change_from_summary=draft.parsed_request.change_from_summary,
            change_to_summary=draft.parsed_request.change_to_summary,
            business_reason=draft.business_reason,
            source_channel=draft.source.source_channel,
            channel_id=draft.source.channel_id,
            thread_id=draft.source.thread_id,
            source_message_id=draft.source.source_message_id,
        )

        payload = self._request_service.get_request_summary(record.request_id)
        if self._notify_approver:
            self._notify_approver(payload)

        return {
            "status": "submitted",
            "message": (
                f"Request {record.request_id} submitted to "
                f"{draft.parsed_request.approver_handle}."
            ),
            "request": payload,
        }
