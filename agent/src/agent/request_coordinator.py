from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from agent.ai.intent_types import (
    AssistedParseResult,
    IntentManagement,
    IntentNewRequest,
    IntentUnknown,
)
from agent.domain.enums import Operation, ResponseStatus
from agent.domain.models import (
    ActorContext,
    AssistantMetadata,
    ChangeRequest,
    CoordinatorResponse,
    MessageSource,
    RequestSummary,
    StructuredCodeSection,
    StructuredRequestPayload,
    UiResponseRequest,
    WorkflowAction,
)
from agent.draft_manager import DraftManager, PendingDraft
from agent.parsing.intent_router import FreeformIntentRouter, RoutedIntent
from agent.parsing.request_parser import (
    ParsedRequest,
    format_confirmation_message,
    list_missing_required_fields,
    parse_request_text,
)
from agent.services.query_service import RequestQueryService
from agent.services.request_service import (
    RequestNotFoundError,
    RequestService,
)
from agent.services.workflow_transitions import InvalidTransitionError
from agent.web.ws_messages import build_request_ui_response

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent.ai.assistant import RequestInputAssistant
    from agent.memory.agent_memory import AgentMemoryService
    from agent.persistence.base import WorkflowStore
    from agent.services.audit_service import AuditService

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
        memory_service: AgentMemoryService | None = None,
        workflow_store: WorkflowStore | None = None,
    ) -> None:
        self._request_service = request_service
        self._audit_service = audit_service
        self._input_assistant = input_assistant
        self._memory = memory_service
        self._drafts = DraftManager(workflow_store=workflow_store)
        self._queries = RequestQueryService(
            request_service=request_service,
            audit_service=audit_service,
            input_assistant=input_assistant,
        )
        self._notify_approver: Callable[[RequestSummary, str | None], None] | None = None
        self._notify_requester: Callable[[str, str], None] | None = None
        self._intent_router = FreeformIntentRouter()
        self._ai_executor = ThreadPoolExecutor(max_workers=2)

    def set_approver_notification_callback(
        self, callback: Callable[[RequestSummary, str | None], None]
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

    _MAX_INPUT_LEN = 2000  # Telegram max is 4096; cap before LLM to limit token spend

    def handle_requester_message(
        self,
        *,
        text: str,
        requester: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        normalized = text.strip()[: self._MAX_INPUT_LEN]
        if self._memory:
            self._memory.log_user_message(requester.handle, normalized)

        if normalized.lower() in {"/confirm", "confirm"}:
            return self._confirm_pending_draft(requester=requester)
        if normalized.lower() in {"/discard", "discard"}:
            return self.discard_draft(requester.handle)

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

        if self._memory and action.action in (Operation.APPROVE, Operation.REJECT):
            request_payload = self._request_service.get_request_summary(record.request_id)
            self._memory.log_approver_decision(
                approver_handle=actor.handle,
                target=request_payload.get("target_label", ""),
                action=action.action.value,
                change_from=request_payload.get("change_from_summary", ""),
                change_to=request_payload.get("change_to_summary", ""),
            )

        request_payload = self._request_service.get_request_summary(record.request_id)
        result_message = _format_action_result_message(
            self._input_assistant,
            action=action.action,
            request=request_payload,
            actor_handle=actor.handle,
            note=action.note,
        )
        same_web_actor = (
            record.requester_handle.strip().casefold() == actor.handle.strip().casefold()
            and (record.origin_channel_id or "").strip().casefold() == actor.handle.strip().casefold()
        )
        if self._notify_requester and record.origin_channel_id and not same_web_actor:
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

    def handle_web_structured_request(
        self,
        *,
        payload: StructuredRequestPayload | dict[str, object],
        requester: ActorContext,
        source: MessageSource,
    ) -> CoordinatorResponse:
        structured_payload = _normalize_structured_payload(payload)
        memory_text = _build_structured_request_text(structured_payload)
        request_text = _extract_structured_request_text(structured_payload)

        if self._memory and memory_text:
            self._memory.log_user_message(requester.handle, memory_text[: self._MAX_INPUT_LEN])

        if not _has_structured_content(structured_payload):
            body = "Add a request description or Before/After content before routing."
            return {
                "status": ResponseStatus.ERROR,
                "message": body,
                "ui_response": {
                    "kind": "error",
                    "title": "Nothing to route",
                    "body": body,
                    "status": ResponseStatus.ERROR,
                },
            }

        impact_note: str | None = None
        approver_handle = str(structured_payload.get("approver", "")).strip()
        if approver_handle and self._input_assistant:
            impact_note = self._input_assistant.generate_impact_note(
                target_label=_derive_target_label(structured_payload),
                change_from=_summarize_structured_section(structured_payload, "before"),
                change_to=_summarize_structured_section(structured_payload, "after"),
            )

        change = ChangeRequest(
            approver_handle=structured_payload["approver"],
            target_label=_derive_target_label(structured_payload),
            change_from_summary=_summarize_structured_section(structured_payload, "before"),
            change_to_summary=_summarize_structured_section(structured_payload, "after"),
            impact_note=impact_note,
            request_text=request_text,
            business_reason=None,
            structured_payload_json=json.dumps(
                structured_payload, separators=(",", ":"), ensure_ascii=True,
            ),
        )
        record = self._request_service.create_request(
            requester=requester,
            change=change,
            source=source,
        )
        request_payload = self._request_service.get_request_summary(record.request_id)

        if self._memory:
            self._memory.log_submission(
                requester_handle=requester.handle,
                target=request_payload.get("target_label", ""),
                approver=request_payload.get("approver_handle", ""),
            )

        if approver_handle and self._notify_approver:
            self._notify_approver(request_payload, impact_note)

        if approver_handle:
            title = f"Request {record.request_id} routed"
            body = f"Queued for {approver_handle} with the structured payload preserved for web review."
            message = f"Request {record.request_id} submitted to {approver_handle}."
        else:
            title = f"Request {record.request_id} saved"
            body = (
                "Saved without an approver. The raw request JSON is preserved so web UI "
                "can assign or review later."
            )
            message = f"Request {record.request_id} saved without an approver."

        return {
            "status": ResponseStatus.SUBMITTED,
            "message": message,
            "request": request_payload,
            "ui_response": build_request_ui_response(
                request_payload,
                kind="request_submitted",
                title=title,
                body=body,
                impact_note=impact_note,
            ).model_dump(mode="json", exclude_none=True),
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
                    impact_note=existing.impact_note,
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
        return self._queries.lookup_request(request_id, actor_handle)

    def get_history(self, request_id: str) -> CoordinatorResponse:
        return self._queries.get_history(request_id)

    def search_by_target(self, target_name: str) -> CoordinatorResponse:
        return self._queries.search_by_target(target_name)

    def list_requester_pending(self, requester_handle: str) -> CoordinatorResponse:
        return self._queries.list_requester_pending(requester_handle)

    def list_pending_approvals(self, approver_handle: str) -> CoordinatorResponse:
        return self._queries.list_pending_approvals(approver_handle)

    # --- private helpers ---

    def _confirm_pending_draft(self, *, requester: ActorContext) -> CoordinatorResponse:
        draft = self._drafts.pop_draft(requester.handle)

        if draft is None:
            return {
                "status": ResponseStatus.ERROR,
                "message": "No pending draft found. Send a request message first.",
            }

        impact_note: str | None = None
        if self._input_assistant:
            impact_note = self._input_assistant.generate_impact_note(
                target_label=draft.parsed_request.target_label,
                change_from=draft.parsed_request.change_from_summary,
                change_to=draft.parsed_request.change_to_summary,
            )

        record = self._request_service.create_request(
            requester=requester,
            change=ChangeRequest(
                approver_handle=draft.parsed_request.approver_handle,
                target_label=draft.parsed_request.target_label,
                change_from_summary=draft.parsed_request.change_from_summary,
                change_to_summary=draft.parsed_request.change_to_summary,
                impact_note=impact_note,
                business_reason=draft.business_reason,
                request_text=draft.request_text,
            ),
            source=draft.source,
        )

        payload = self._request_service.get_request_summary(record.request_id)
        if self._memory:
            self._memory.log_submission(
                requester_handle=draft.requester.handle,
                target=draft.parsed_request.target_label,
                approver=draft.parsed_request.approver_handle,
            )
        if self._notify_approver and draft.parsed_request.approver_handle.strip():
            self._notify_approver(payload, impact_note)

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

        user_context = self._memory.get_user_preferences(requester.handle) if self._memory else None

        # Speculative parallel execution: run classify and assist concurrently so the
        # total latency is max(classify, assist) instead of their sum (~0.5-1.5s vs ~1-3s).
        # If classify returns a management op or unknown, the assist result is discarded.
        intent_fut = self._ai_executor.submit(self._input_assistant.classify_intent, text, user_context)
        assist_fut = self._ai_executor.submit(self._input_assistant.assist_request_text, text, user_context)
        intent = intent_fut.result()
        assist_result = assist_fut.result()

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

        # IntentNewRequest: use pre-fetched assist result (already running in parallel)
        outcome = self._resolve_new_request(text, intent, assist_result=assist_result)
        return self._build_draft_response(outcome=outcome, requester=requester, source=source)

    def _resolve_new_request(
        self,
        text: str,
        intent: IntentNewRequest,
        assist_result: AssistedParseResult,
    ) -> ParseOutcome:
        pre_parsed = ParsedRequest(
            target_label=intent.target_label,
            change_from_summary=intent.change_from_summary,
            change_to_summary=intent.change_to_summary,
            approver_handle=intent.approver_handle,
        )
        if not list_missing_required_fields(pre_parsed):
            # classify returned complete fields — use them directly, discard assist_result
            return ParseOutcome(
                text=text,
                parsed=pre_parsed,
                parser_name="llm_assisted",
                assisted_result=AssistedParseResult(
                    parsed_request=pre_parsed,
                    guidance_message=intent.guidance_message,
                    parser_name="llm_assisted",
                ),
            )
        # Fields incomplete — use the assist result that was fetched concurrently
        return ParseOutcome(
            text=text,
            parsed=assist_result.parsed_request,
            parser_name="llm_assisted",
            assisted_result=assist_result,
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
        draft_payload = {
            "requester_handle": requester.handle,
            "approver_handle": outcome.parsed.approver_handle,
            "target_label": outcome.parsed.target_label,
            "change_from_summary": outcome.parsed.change_from_summary,
            "change_to_summary": outcome.parsed.change_to_summary,
            "parser": outcome.parser_name,
        }
        return {
            "status": ResponseStatus.MISSING_FIELDS,
            "message": (
                clarification
                or (outcome.assisted_result.guidance_message if outcome.assisted_result else None)
                or f"Missing fields: {', '.join(missing_fields)}"
            ),
            "missing_fields": missing_fields,
            "draft": draft_payload,
            "parser": outcome.parser_name,
            "parser_metadata": _assistant_metadata(outcome.assisted_result),
            "ui_response": {
                "kind": "missing_fields",
                "title": "Need more info",
                "body": (
                    clarification
                    or (outcome.assisted_result.guidance_message if outcome.assisted_result else None)
                    or f"Missing fields: {', '.join(missing_fields)}"
                ),
                "status": ResponseStatus.MISSING_FIELDS,
                "missing_fields": missing_fields,
                "guidance_message": (
                    clarification
                    or (outcome.assisted_result.guidance_message if outcome.assisted_result else None)
                    or f"Missing fields: {', '.join(missing_fields)}"
                ),
                "draft": draft_payload,
            },
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
            "ui_response": {
                "kind": "confirmation_required",
                "title": "Draft ready to submit",
                "body": "Review the extracted fields, then confirm to route the request.",
                "status": ResponseStatus.CONFIRMATION_REQUIRED,
                "draft": {
                    "requester_handle": requester.handle,
                    "approver_handle": draft.parsed_request.approver_handle,
                    "target_label": draft.parsed_request.target_label,
                    "change_from_summary": draft.parsed_request.change_from_summary,
                    "change_to_summary": draft.parsed_request.change_to_summary,
                    "parser": outcome.parser_name,
                },
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
            Operation.APPROVE: _approver_action,
            Operation.REJECT: _approver_action,
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
    "- 'enable feature-X on api-gateway, ask annie@example.com to approve'\n"
    "- 'change timeout from 30s to 60s for nginx-config, @ops should review'\n"
    "- 'tắt tính năng beta, nhờ manager@example.com duyệt'"
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



_REQUESTER_NOTIFICATION_TEMPLATES: dict[Operation, str] = {
    Operation.APPROVE:  "✅ {request_id} has been approved by {actor_handle}.{note_line}",
    Operation.REJECT:   "❌ {request_id} has been rejected by {actor_handle}.{note_line}",
    Operation.NEEDINFO: (
        "Info: {actor_handle} needs more information on {request_id}.{note_line}\n"
        "Just reply with your updated message to resubmit."
    ),
    Operation.CANCEL:   "🚫 {request_id} was cancelled by {actor_handle}.{note_line}",
}


def _format_requester_notification(
    *,
    action: Operation,
    request_id: str,
    actor_handle: str,
    note: str,
) -> str:
    note_line = f"\nNote: {note}" if note else ""
    template = _REQUESTER_NOTIFICATION_TEMPLATES.get(
        action, "{request_id} status updated by {actor_handle}.{note_line}"
    )
    return template.format(request_id=request_id, actor_handle=actor_handle, note_line=note_line)


def _normalize_structured_payload(
    payload: StructuredRequestPayload | dict[str, object],
) -> StructuredRequestPayload:
    raw = payload if isinstance(payload, dict) else {}
    mode = raw.get("mode")
    request_format = raw.get("request_format")
    normalized_mode = (
        mode if mode in ("free_text", "config_change", "object_change") else "free_text"
    )
    normalized_request_format = (
        request_format if request_format in ("text", "yaml", "json") else "text"
    )
    return {
        "mode": cast("StructuredRequestPayload['mode']", normalized_mode),
        "request_format": cast("StructuredRequestPayload['request_format']", normalized_request_format),
        "request": _coerce_raw_text(raw.get("request")),
        "approver": _clean_text(raw.get("approver")),
        "before": _normalize_structured_section(raw.get("before")),
        "after": _normalize_structured_section(raw.get("after")),
    }


def _normalize_structured_section(raw: object) -> StructuredCodeSection:
    if not isinstance(raw, dict):
        return {"enabled": False, "format": "yaml", "value": ""}

    value = raw.get("value")
    text = _coerce_raw_text(value)
    format_value = raw.get("format") if raw.get("format") in ("text", "yaml", "json") else "yaml"
    enabled = bool(raw.get("enabled")) or bool(text.strip())
    return {
        "enabled": enabled,
        "format": format_value,
        "value": text,
    }


def _clean_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()


def _coerce_raw_text(value: object) -> str:
    if not isinstance(value, str):
        return ""
    return value.replace("\r\n", "\n")


def _has_structured_content(payload: StructuredRequestPayload) -> bool:
    return bool(
        payload["request"].strip()
        or _has_structured_section(payload["before"])
        or _has_structured_section(payload["after"])
    )


def _has_structured_section(section: StructuredCodeSection) -> bool:
    return section["enabled"] and bool(section["value"].strip())


def _build_structured_request_text(payload: StructuredRequestPayload) -> str:
    parts: list[str] = []
    request = payload["request"].strip()

    if request:
        parts.append(request)

    if payload["mode"] != "free_text":
        type_label = "Config change" if payload["mode"] == "config_change" else "Object from/to"
        parts.insert(0, f"Type: {type_label}")

    if payload["approver"].strip():
        parts.append(f"Approver: {payload['approver'].strip()}")

    for key in ("before", "after"):
        section = payload[key]
        if not _has_structured_section(section):
            continue
        title = _section_title(payload["mode"], cast("str", key))
        parts.append(f"{title} ({section['format']})")
        parts.append(f"```{section['format']}\n{section['value'].rstrip()}\n```")

    return "\n\n".join(parts).strip()


def _extract_structured_request_text(payload: StructuredRequestPayload) -> str:
    return payload["request"].replace("\r\n", "\n")


def _derive_target_label(payload: StructuredRequestPayload) -> str:
    request = _collapse_whitespace(payload["request"])
    if request:
        return _truncate(request, 96)
    if payload["mode"] == "config_change":
        return "Config change"
    if payload["mode"] == "object_change":
        return "Object change"
    return "Change request"


def _summarize_structured_section(
    payload: StructuredRequestPayload,
    key: str,
) -> str:
    section = payload[key]
    if _has_structured_section(section):
        line_count = max(1, len(section["value"].splitlines()))
        title = _section_title(payload["mode"], key)
        suffix = "line" if line_count == 1 else "lines"
        return f"{title} {section['format']} block ({line_count} {suffix})"

    if key == "after" and payload["request"]:
        return _truncate(_collapse_whitespace(payload["request"]), 120)

    return "Not provided"


def _section_title(mode: str, key: str) -> str:
    if mode == "object_change":
        return "From" if key == "before" else "To"
    return "Before" if key == "before" else "After"


def _collapse_whitespace(text: str) -> str:
    return " ".join(text.split())


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _to_ui_request(request: RequestSummary) -> UiResponseRequest:
    return {
        "request_id": request["request_id"],
        "requester_handle": request["requester_handle"],
        "approver_handle": request["approver_handle"],
        "target_label": request["target_label"],
        "change_from_summary": request["change_from_summary"],
        "change_to_summary": request["change_to_summary"],
        "review_status": request["review_status"],
        "request_text": request.get("request_text", ""),
        "structured_payload": request.get("structured_payload"),
    }
