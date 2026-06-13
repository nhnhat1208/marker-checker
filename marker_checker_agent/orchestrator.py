from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from marker_checker_agent.ai_input_assistance import (
    AssistedParseResult,
    RequestInputAssistant,
)
from marker_checker_agent.domain.enums import AuditEventType
from marker_checker_agent.intent_router import FreeformIntentRouter, RoutedIntent
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
        self._pending_drafts: dict[str, PendingDraft] = {}
        self._draft_lock = threading.Lock()
        self._notify_approver: Callable[[dict[str, Any]], None] | None = None
        self._intent_router = FreeformIntentRouter()

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

        routed_intent = self._intent_router.route(normalized)
        if routed_intent:
            return self._execute_routed_intent(
                routed_intent,
                actor_name=requester_name,
                actor_handle=requester_handle,
                source=source,
            )

        parsed = parse_request_text(normalized)
        parser_name = "pattern"
        assisted_result: AssistedParseResult | None = None
        if not parsed and self._input_assistant:
            assisted_result = self._input_assistant.assist_request_text(normalized)
            parsed = assisted_result.parsed_request
            parser_name = assisted_result.parser_name

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
            clarification_message = (
                self._input_assistant.generate_clarification_message(
                    original_message=normalized,
                    missing_fields=missing_fields,
                    validation_errors=assisted_result.validation_errors or [],
                )
                if self._input_assistant
                else None
            )
            return {
                "status": "missing_fields",
                "message": (
                    clarification_message
                    or (
                        assisted_result.guidance_message
                        if assisted_result and assisted_result.guidance_message
                        else None
                    )
                    or (
                        f"Missing fields: {', '.join(missing_fields)}"
                    )
                ),
                "missing_fields": missing_fields,
                "parser": parser_name,
                "parser_metadata": (
                    {
                        "model": assisted_result.model,
                        "prompt_version": assisted_result.prompt_version,
                        "latency_ms": assisted_result.latency_ms,
                        "validation_errors": assisted_result.validation_errors or [],
                    }
                    if assisted_result
                    else None
                ),
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
            "message": self._format_draft_confirmation(
                draft.parsed_request,
                parser_name=parser_name,
            ),
            "draft": {
                "requester_handle": requester_handle,
                "approver_handle": draft.parsed_request.approver_handle,
                "target_label": draft.parsed_request.target_label,
                "change_from_summary": draft.parsed_request.change_from_summary,
                "change_to_summary": draft.parsed_request.change_to_summary,
                "parser": parser_name,
                "parser_metadata": (
                    {
                        "model": assisted_result.model,
                        "prompt_version": assisted_result.prompt_version,
                        "latency_ms": assisted_result.latency_ms,
                        "validation_errors": assisted_result.validation_errors or [],
                    }
                    if assisted_result
                    else None
                ),
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

        request_payload = self._request_service.get_request_summary(record.request_id)
        return {
            "status": "ok",
            "message": self._format_action_result_message(
                action=action,
                request=request_payload,
                actor_handle=actor_handle,
                note=note,
            ),
            "request": request_payload,
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
        return {
            "status": "ok",
            "request": request,
            "summary_message": self._generate_request_status_summary(request),
        }

    def get_history(self, request_id: str) -> dict[str, Any]:
        timeline = self._audit_service.list_timeline(request_id)
        history_payload = [
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
            "status": "ok",
            "timeline": history_payload,
            "summary_message": self._generate_request_history_summary(history_payload),
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

    def _format_draft_confirmation(
        self,
        parsed_request: ParsedRequest,
        *,
        parser_name: str,
    ) -> str:
        default_message = format_confirmation_message(parsed_request)
        summary = (
            f"target: {parsed_request.target_label}\n"
            f"from: {parsed_request.change_from_summary}\n"
            f"to: {parsed_request.change_to_summary}\n"
            f"approver: {parsed_request.approver_handle}"
        )
        llm_message = (
            self._input_assistant.generate_confirmation_message(
                parsed_request_summary=summary
            )
            if self._input_assistant
            else None
        )
        message = llm_message or default_message
        if parser_name == "llm_assisted":
            return f"LLM-assisted draft detected. Please verify the fields carefully.\n\n{message}"
        return message

    def _execute_routed_intent(
        self,
        routed_intent: RoutedIntent,
        *,
        actor_name: str | None,
        actor_handle: str,
        source: MessageSource,
    ) -> dict[str, Any]:
        if routed_intent.operation == "lookup":
            return self.lookup_request(
                request_id=routed_intent.request_id,
                actor_handle=actor_handle,
            )
        if routed_intent.operation == "history":
            return self.get_history(routed_intent.request_id)
        if routed_intent.operation == "cancel":
            return self.handle_approver_action(
                action="cancel",
                request_id=routed_intent.request_id,
                actor_name=actor_name,
                actor_handle=actor_handle,
                note=routed_intent.note,
                source=source,
            )
        if routed_intent.operation == "needinfo":
            return self.handle_approver_action(
                action="needinfo",
                request_id=routed_intent.request_id,
                actor_name=actor_name,
                actor_handle=actor_handle,
                note=routed_intent.note,
                source=source,
            )
        if routed_intent.operation == "resubmit":
            return self.handle_resubmission(
                request_id=routed_intent.request_id,
                text=routed_intent.text,
                actor_name=actor_name,
                actor_handle=actor_handle,
                source=source,
            )
        if routed_intent.operation == "my_pending":
            return self.list_requester_pending(actor_handle)
        if routed_intent.operation == "pending_approvals":
            return self.list_pending_approvals(actor_handle)
        return {
            "status": "error",
            "message": f"Unsupported routed operation: {routed_intent.operation}",
        }

    def list_requester_pending(self, requester_handle: str) -> dict[str, Any]:
        requests = self._request_service.list_requester_pending_summaries(requester_handle)
        return {
            "status": "ok",
            "message": self._format_request_list_message(
                requests,
                empty_message="You have no active requests.",
                title="Your active requests:",
            ),
            "requests": requests,
        }

    def list_pending_approvals(self, approver_handle: str) -> dict[str, Any]:
        requests = self._request_service.list_approver_pending_summaries(approver_handle)
        return {
            "status": "ok",
            "message": self._format_request_list_message(
                requests,
                empty_message="You have no requests waiting for approval.",
                title="Requests waiting for your approval:",
            ),
            "requests": requests,
        }

    def _generate_request_status_summary(self, request: dict[str, Any]) -> str | None:
        if not self._input_assistant:
            return None
        summary = (
            f"request_id: {request.get('request_id', '')}\n"
            f"status: {request.get('review_status', '')}\n"
            f"target: {request.get('target_label', '')}\n"
            f"from: {request.get('change_from_summary', '')}\n"
            f"to: {request.get('change_to_summary', '')}\n"
            f"requester: {request.get('requester_handle', '')}\n"
            f"approver: {request.get('approver_handle', '')}\n"
            f"revision: {request.get('last_submitted_revision', '')}"
        )
        return self._input_assistant.generate_status_summary(request_summary=summary)

    def _generate_request_history_summary(
        self,
        history_payload: list[dict[str, Any]],
    ) -> str | None:
        if not self._input_assistant or not history_payload:
            return None
        history_lines = [
            (
                f"{event['event_sequence']}. {event['event_type']} | "
                f"{event['summary']} | actor={event['actor_handle']} | "
                f"at={event['occurred_at']}"
            )
            for event in history_payload
        ]
        return self._input_assistant.generate_history_summary(
            request_history="\n".join(history_lines)
        )

    def _format_action_result_message(
        self,
        *,
        action: str,
        request: dict[str, Any],
        actor_handle: str,
        note: str,
    ) -> str:
        default_message = (
            f"{request.get('request_id', '')} moved to {request.get('review_status', '')}."
        )
        if not self._input_assistant:
            return default_message
        action_result = (
            f"action: {action}\n"
            f"request_id: {request.get('request_id', '')}\n"
            f"status: {request.get('review_status', '')}\n"
            f"target: {request.get('target_label', '')}\n"
            f"from: {request.get('change_from_summary', '')}\n"
            f"to: {request.get('change_to_summary', '')}\n"
            f"actor: {actor_handle}\n"
            f"note: {note}"
        )
        return (
            self._input_assistant.generate_action_result_message(
                action_result=action_result
            )
            or default_message
        )

    def _format_request_list_message(
        self,
        requests: list[dict[str, Any]],
        *,
        empty_message: str,
        title: str,
    ) -> str:
        if not requests:
            return empty_message
        lines = [title]
        for request in requests[:5]:
            lines.append(
                (
                    f"- {request.get('request_id')} | {request.get('review_status')} | "
                    f"{request.get('target_label')} | "
                    f"{request.get('change_from_summary')} -> {request.get('change_to_summary')}"
                )
            )
        if len(requests) > 5:
            lines.append(f"... and {len(requests) - 5} more.")
        return "\n".join(lines)
