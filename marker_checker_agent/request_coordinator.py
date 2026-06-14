from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from marker_checker_agent.ai.intent_types import (
    AssistedParseResult,
    IntentManagement,
    IntentNewRequest,
    IntentUnknown,
)
from marker_checker_agent.domain.enums import ActorKind, AuditEventType, Operation, ResponseStatus
from marker_checker_agent.domain.models import (
    ActorContext,
    AssistantMetadata,
    AuditEventInput,
    ChangeRequest,
    CoordinatorResponse,
    MessageSource,
    RequestSummary,
    TimelineEvent,
    WorkflowAction,
)
from marker_checker_agent.draft_manager import DraftManager, PendingDraft
from marker_checker_agent.parsing.intent_router import FreeformIntentRouter, RoutedIntent
from marker_checker_agent.parsing.request_parser import (
    ParsedRequest,
    format_confirmation_message,
    list_missing_required_fields,
    parse_request_text,
)
from marker_checker_agent.services.request_service import (
    RequestNotFoundError,
    RequestService,
)
from marker_checker_agent.services.workflow_transitions import InvalidTransitionError

if TYPE_CHECKING:
    from collections.abc import Callable

    from marker_checker_agent.ai.assistant import RequestInputAssistant
    from marker_checker_agent.services.audit_service import AuditService

LOGGER = logging.getLogger(__name__)


@dataclass
class ParseOutcome:
    text: str
    parsed: ParsedRequest | None
    parser_name: str
    assisted_result: AssistedParseResult | None


class RequestCoordinator:
    """Application service that coordinates change-request conversations end-to-end.

    Bridges the inbound channel (Telegram, HTTP API) with the domain services
    (RequestService, AuditService) by routing user messages, managing draft state,
    and dispatching notifications.
    """

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
        self._drafts = DraftManager()
        self._notify_approver: Callable[[RequestSummary], None] | None = None
        self._notify_requester: Callable[[str, str], None] | None = None
        self._intent_router = FreeformIntentRouter()

    def set_approver_notification_callback(
        self, callback: Callable[[RequestSummary], None]
    ) -> None:
        self._notify_approver = callback

    def set_requester_notification_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        self._notify_requester = callback

    def discard_draft(self, requester_handle: str) -> CoordinatorResponse:
        if not self._drafts.discard_all(requester_handle):
            return {"status": ResponseStatus.ERROR, "message": "No pending draft to discard."}
        return {"status": ResponseStatus.OK, "message": "Pending draft discarded."}

    def handle_requester_message(
        self,
        *,
        text: str,
        requester: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        normalized = text.strip()

        if normalized.lower() == "/confirm":
            return self._confirm_pending_draft(requester=requester)

        routed = self._intent_router.route(normalized)
        if routed:
            return self._execute_routed_intent(routed, actor=requester, source=source)

        # Fast-path: exact rigid pattern, no LLM required
        parsed = parse_request_text(normalized)
        if parsed:
            self._drafts.reset_for_new_request(requester.handle)
            return self._build_draft_response(
                outcome=ParseOutcome(
                    text=normalized, parsed=parsed, parser_name="pattern", assisted_result=None
                ),
                requester=requester,
                source=source,
            )

        # Contextual resubmit: user received NEEDINFO, their next free-text = resubmission
        pending_request_id = self._drafts.pop_resubmit(requester.handle)
        if pending_request_id is not None:
            return self.handle_resubmission(
                request_id=pending_request_id,
                text=normalized,
                actor=requester,
                source=source,
            )

        if not self._input_assistant:
            return {"status": ResponseStatus.NEEDS_INPUT, "message": _NEEDS_INPUT_MESSAGE}

        return self._handle_with_ai(text=normalized, requester=requester, source=source)

    def handle_approver_action(
        self,
        *,
        actor: ActorContext,
        action: WorkflowAction,
        source: MessageSource,
    ) -> CoordinatorResponse:
        dispatch = {
            Operation.APPROVE: self._request_service.approve_request,
            Operation.REJECT: self._request_service.reject_request,
            Operation.NEEDINFO: self._request_service.request_more_info,
            Operation.CANCEL: self._request_service.cancel_request,
        }
        handler = dispatch.get(action.action)
        if handler is None:
            return {"status": ResponseStatus.ERROR, "message": f"Unsupported action: {action.action}"}
        try:
            record = handler(request_id=action.request_id, actor=actor, note=action.note, source=source)
        except (InvalidTransitionError, RequestNotFoundError, ValueError) as exc:
            return {"status": ResponseStatus.ERROR, "message": str(exc)}

        if action.action == Operation.NEEDINFO:
            self._drafts.set_resubmit(record.requester_handle, record.request_id)
        elif action.action in (Operation.APPROVE, Operation.REJECT, Operation.CANCEL):
            self._drafts.clear_resubmit(record.requester_handle)

        request_payload = self._request_service.get_request_summary(record.request_id)
        result_message = _format_action_result_message(
            self._input_assistant,
            action=action.action,
            request=request_payload,
            actor_handle=actor.handle,
            note=action.note,
        )
        if self._notify_requester and record.origin_channel_id:
            requester_msg = _format_requester_notification(
                action=action.action,
                request_id=record.request_id,
                actor_handle=actor.handle,
                note=action.note,
            )
            self._notify_requester(record.origin_channel_id, requester_msg)
        return {
            "status": ResponseStatus.OK,
            "message": result_message,
            "request": request_payload,
        }

    def handle_resubmission(
        self,
        *,
        request_id: str,
        text: str,
        actor: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        parsed, early = self._parse_resubmission_text(text)
        if early is not None:
            return early
        if not parsed:
            return {"status": ResponseStatus.ERROR, "message": "Could not parse resubmission message."}

        try:
            existing = self._request_service.get_request(request_id)
            record = self._request_service.resubmit_request(
                request_id=request_id,
                actor=actor,
                change=ChangeRequest(
                    approver_handle=existing.approver_handle,
                    target_label=parsed.target_label,
                    change_from_summary=parsed.change_from_summary,
                    change_to_summary=parsed.change_to_summary,
                    business_reason=None,
                    request_text=text,
                ),
                source=source,
            )
        except (InvalidTransitionError, RequestNotFoundError) as exc:
            return {"status": ResponseStatus.ERROR, "message": str(exc)}

        return {
            "status": ResponseStatus.OK,
            "message": f"{record.request_id} resubmitted as revision {record.last_submitted_revision}.",
            "request": self._request_service.get_request_summary(record.request_id),
        }

    def _parse_resubmission_text(
        self, text: str
    ) -> tuple[ParsedRequest | None, CoordinatorResponse | None]:
        parsed = parse_request_text(text)
        if parsed or not self._input_assistant:
            return parsed, None

        result = self._input_assistant.assist_request_text(text)
        if not result.parsed_request:
            return None, None

        missing = list_missing_required_fields(result.parsed_request)
        if missing:
            return None, {
                "status": ResponseStatus.MISSING_FIELDS,
                "message": result.guidance_message or f"Missing fields: {', '.join(missing)}",
                "missing_fields": missing,
            }
        return result.parsed_request, None

    def lookup_request(self, request_id: str, actor_handle: str) -> CoordinatorResponse:
        try:
            request = self._request_service.get_request_summary(request_id)
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
        requests = self._request_service.search_by_target_label(target_name)
        return {
            "status": ResponseStatus.OK,
            "message": _format_request_list(
                requests,
                empty_message=f"No requests found for target '{target_name}'.",
                title=f"Requests for '{target_name}':",
            ),
            "requests": requests,
        }

    def list_requester_pending(self, requester_handle: str) -> CoordinatorResponse:
        requests = self._request_service.list_requester_pending_summaries(requester_handle)
        return {
            "status": ResponseStatus.OK,
            "message": _format_request_list(
                requests,
                empty_message="You have no active requests.",
                title="Your active requests:",
            ),
            "requests": requests,
        }

    def list_pending_approvals(self, approver_handle: str) -> CoordinatorResponse:
        requests = self._request_service.list_approver_pending_summaries(approver_handle)
        return {
            "status": ResponseStatus.OK,
            "message": _format_request_list(
                requests,
                empty_message="You have no requests waiting for approval.",
                title="Requests waiting for your approval:",
            ),
            "requests": requests,
        }

    # --- private helpers ---

    def _confirm_pending_draft(self, *, requester: ActorContext) -> CoordinatorResponse:
        draft = self._drafts.pop_draft(requester.handle)

        if draft is None:
            return {
                "status": ResponseStatus.ERROR,
                "message": "No pending draft found. Send a request message first.",
            }

        record = self._request_service.create_request(
            requester=requester,
            change=ChangeRequest(
                approver_handle=draft.parsed_request.approver_handle,
                target_label=draft.parsed_request.target_label,
                change_from_summary=draft.parsed_request.change_from_summary,
                change_to_summary=draft.parsed_request.change_to_summary,
                business_reason=draft.business_reason,
                request_text=draft.request_text,
            ),
            source=draft.source,
        )

        payload = self._request_service.get_request_summary(record.request_id)
        if self._notify_approver:
            self._notify_approver(payload)

        return {
            "status": ResponseStatus.SUBMITTED,
            "message": (
                f"Request {record.request_id} submitted to "
                f"{draft.parsed_request.approver_handle}."
            ),
            "request": payload,
        }

    def _handle_with_ai(
        self,
        *,
        text: str,
        requester: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        assert self._input_assistant is not None
        # Short reply after MISSING_FIELDS: combine with original to fill in the missing field.
        text = self._drafts.combine_partial_if_short(requester.handle, text)

        intent = self._input_assistant.classify_intent(text)

        if isinstance(intent, IntentManagement):
            if intent.operation == Operation.CONFIRM:
                return self._confirm_pending_draft(requester=requester)
            routed = RoutedIntent(
                operation=intent.operation,
                request_id=intent.request_id,
                note=intent.note,
                text=intent.text,
                target_name=intent.target_name,
            )
            return self._execute_routed_intent(routed, actor=requester, source=source)

        if isinstance(intent, IntentUnknown):
            return {"status": ResponseStatus.NEEDS_INPUT, "message": _NEEDS_INPUT_MESSAGE}

        # IntentNewRequest: use fields from classify if complete, else fall back to assist
        outcome = self._resolve_new_request(text, intent)
        return self._build_draft_response(outcome=outcome, requester=requester, source=source)

    def _resolve_new_request(self, text: str, intent: IntentNewRequest) -> ParseOutcome:
        assert self._input_assistant is not None
        pre_parsed = ParsedRequest(
            target_label=intent.target_label,
            change_from_summary=intent.change_from_summary,
            change_to_summary=intent.change_to_summary,
            approver_handle=intent.approver_handle,
        )
        if not list_missing_required_fields(pre_parsed):
            assisted = AssistedParseResult(
                parsed_request=pre_parsed,
                guidance_message=intent.guidance_message,
                parser_name="llm_assisted",
            )
            return ParseOutcome(
                text=text, parsed=pre_parsed, parser_name="llm_assisted", assisted_result=assisted
            )
        assisted = self._input_assistant.assist_request_text(text)
        return ParseOutcome(
            text=text, parsed=assisted.parsed_request, parser_name="llm_assisted", assisted_result=assisted
        )

    def _build_draft_response(
        self,
        *,
        outcome: ParseOutcome,
        requester: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        if not outcome.parsed:
            return {"status": ResponseStatus.NEEDS_INPUT, "message": _NEEDS_INPUT_MESSAGE}
        missing_fields = list_missing_required_fields(outcome.parsed)
        if missing_fields:
            return self._missing_fields_response(outcome, requester, missing_fields)
        return self._draft_confirmation_response(outcome, requester, source)

    def _missing_fields_response(
        self,
        outcome: ParseOutcome,
        requester: ActorContext,
        missing_fields: list[str],
    ) -> CoordinatorResponse:
        assert outcome.parsed is not None
        validation_errors = outcome.assisted_result.validation_errors if outcome.assisted_result else []
        clarification = (
            self._input_assistant.generate_clarification_message(
                original_message=outcome.text,
                missing_fields=missing_fields,
                validation_errors=validation_errors,
            )
            if self._input_assistant
            else None
        )
        self._drafts.set_partial(requester.handle, outcome.text, outcome.parsed)
        return {
            "status": ResponseStatus.MISSING_FIELDS,
            "message": (
                clarification
                or (outcome.assisted_result.guidance_message if outcome.assisted_result else None)
                or f"Missing fields: {', '.join(missing_fields)}"
            ),
            "missing_fields": missing_fields,
            "parser": outcome.parser_name,
            "parser_metadata": _assistant_metadata(outcome.assisted_result),
        }

    def _draft_confirmation_response(
        self,
        outcome: ParseOutcome,
        requester: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        assert outcome.parsed is not None
        draft = PendingDraft(
            request_text=outcome.text,
            requester=requester,
            parsed_request=outcome.parsed,
            business_reason=None,
            source=source,
        )
        had_existing = self._drafts.set_draft(requester.handle, draft)
        confirmation = _format_draft_confirmation(
            self._input_assistant, draft.parsed_request, parser_name=outcome.parser_name,
        )
        if had_existing:
            confirmation = "⚠️ Previous draft replaced.\n\n" + confirmation
        return {
            "status": ResponseStatus.CONFIRMATION_REQUIRED,
            "message": confirmation,
            "draft": {
                "requester_handle": requester.handle,
                "approver_handle": draft.parsed_request.approver_handle,
                "target_label": draft.parsed_request.target_label,
                "change_from_summary": draft.parsed_request.change_from_summary,
                "change_to_summary": draft.parsed_request.change_to_summary,
                "parser": outcome.parser_name,
                "parser_metadata": _assistant_metadata(outcome.assisted_result),
            },
        }

    def _execute_routed_intent(
        self,
        routed_intent: RoutedIntent,
        *,
        actor: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        op = routed_intent.operation

        def _approver_action() -> CoordinatorResponse:
            return self.handle_approver_action(
                actor=actor,
                action=WorkflowAction(
                    action=op, request_id=routed_intent.request_id, note=routed_intent.note,
                ),
                source=source,
            )

        dispatch: dict[Operation, Callable[[], CoordinatorResponse]] = {
            Operation.CANCEL: _approver_action,
            Operation.NEEDINFO: _approver_action,
            Operation.LOOKUP: lambda: self.lookup_request(
                request_id=routed_intent.request_id, actor_handle=actor.handle,
            ),
            Operation.HISTORY: lambda: self.get_history(routed_intent.request_id),
            Operation.RESUBMIT: lambda: self.handle_resubmission(
                request_id=routed_intent.request_id, text=routed_intent.text, actor=actor, source=source,
            ),
            Operation.MY_PENDING: lambda: self.list_requester_pending(actor.handle),
            Operation.PENDING_APPROVALS: lambda: self.list_pending_approvals(actor.handle),
            Operation.SEARCH: lambda: self.search_by_target(routed_intent.target_name),
        }
        handler = dispatch.get(op)
        if handler is None:
            return {"status": ResponseStatus.ERROR, "message": f"Unsupported routed operation: {op}"}
        return handler()

# Backward-compatible alias.
AgentOrchestrator = RequestCoordinator


# --- module-level helpers (pure functions, no class state) ---

_NEEDS_INPUT_MESSAGE = (
    "Describe your change request in natural language, for example:\n"
    "- 'enable feature-X on api-gateway, ask @john to approve'\n"
    "- 'change timeout from 30s to 60s for nginx-config, @ops should review'\n"
    "- 'tắt tính năng beta, nhờ @manager duyệt'"
)


def _format_draft_confirmation(
    assistant: RequestInputAssistant | None,
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
        assistant.generate_confirmation_message(parsed_request_summary=summary) if assistant else None
    )
    message = llm_message or default_message
    if parser_name == "llm_assisted":
        return f"LLM-assisted draft detected. Please verify the fields carefully.\n\n{message}"
    return message


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


def _format_action_result_message(
    assistant: RequestInputAssistant | None,
    *,
    action: Operation,
    request: RequestSummary,
    actor_handle: str,
    note: str,
) -> str:
    default_message = f"{request['request_id']} moved to {request['review_status']}."
    if not assistant:
        return default_message
    action_result = (
        f"action: {action}\n"
        f"request_id: {request['request_id']}\n"
        f"status: {request['review_status']}\n"
        f"target: {request['target_label']}\n"
        f"from: {request['change_from_summary']}\n"
        f"to: {request['change_to_summary']}\n"
        f"actor: {actor_handle}\n"
        f"note: {note}"
    )
    return assistant.generate_action_result_message(action_result=action_result) or default_message


def _assistant_metadata(result: AssistedParseResult | None) -> AssistantMetadata | None:
    if result is None:
        return None
    return {
        "model": result.model,
        "prompt_version": result.prompt_version,
        "latency_ms": result.latency_ms,
        "validation_errors": result.validation_errors,
    }


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


def _format_requester_notification(
    *,
    action: Operation,
    request_id: str,
    actor_handle: str,
    note: str,
) -> str:
    note_line = f"\nNote: {note}" if note else ""
    if action == Operation.APPROVE:
        return f"✅ {request_id} has been approved by {actor_handle}.{note_line}"
    if action == Operation.REJECT:
        return f"❌ {request_id} has been rejected by {actor_handle}.{note_line}"
    if action == Operation.NEEDINFO:
        return (
            f"ℹ️ {actor_handle} needs more information on {request_id}.{note_line}"  # noqa: RUF001
            "\nJust reply with your updated message to resubmit."
        )
    if action == Operation.CANCEL:
        return f"🚫 {request_id} was cancelled by {actor_handle}.{note_line}"
    return f"{request_id} status updated by {actor_handle}.{note_line}"
