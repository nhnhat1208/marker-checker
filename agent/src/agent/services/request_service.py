from __future__ import annotations

import json
from typing import TYPE_CHECKING
from uuid import uuid4

from agent.domain.enums import ActorKind, AuditEventType, ConversationRole, ReviewStatus
from agent.domain.models import (
    ActorContext,
    AuditEventInput,
    ChangeRequest,
    EventPayload,
    MessageSource,
    RequestConversationRecord,
    RequestRecord,
    RequestSummary,
)
from agent.services.workflow_transitions import validate_transition
from agent.utils.approver_handles import normalize_approver_handle
from agent.utils.text_search import target_match_score
from agent.utils.time_utils import utc_now

if TYPE_CHECKING:
    from datetime import datetime

    from agent.config import RuntimeConfig
    from agent.persistence.base import WorkflowStore
    from agent.services.audit_service import AuditService


class RequestNotFoundError(LookupError):
    """Raised when a request cannot be found."""


class RequestService:

    def __init__(
        self,
        *,
        config: RuntimeConfig,
        workflow_store: WorkflowStore,
        audit_service: AuditService,
    ) -> None:
        self._config = config
        self._workflow_store = workflow_store
        self._audit_service = audit_service

    def create_request(
        self,
        *,
        requester: ActorContext,
        change: ChangeRequest,
        source: MessageSource,
    ) -> RequestRecord:
        request_id = self._generate_request_id()
        now = utc_now()
        approver_handle = normalize_approver_handle(change.approver_handle)

        record = RequestRecord(
            request_id=request_id,
            request_text=change.request_text,
            structured_payload_json=change.structured_payload_json,
            requester_name=requester.name,
            requester_handle=requester.handle,
            approver_name=None,
            approver_handle=approver_handle,
            target_label=change.target_label,
            change_from_summary=change.change_from_summary,
            change_to_summary=change.change_to_summary,
            business_reason=change.business_reason,
            review_status=ReviewStatus.SUBMITTED,
            current_revision=1,
            last_submitted_revision=1,
            last_submitted_at=now,
            created_at=now,
            updated_at=now,
            origin_channel_id=source.channel_id,
            origin_thread_id=source.thread_id,
            origin_message_id=source.source_message_id,
        )
        self._workflow_store.create_request(record)
        self._link_conversation(
            request_id=request_id, actor_handle=requester.handle,
            role=ConversationRole.REQUESTER_FOLLOWUP, source=source, now=now,
        )
        if approver_handle:
            self._link_conversation(
                request_id=request_id,
                actor_handle=approver_handle,
                role=ConversationRole.APPROVER_REVIEW,
                source=MessageSource(
                    source_channel=source.source_channel,
                    channel_id=approver_handle,
                    thread_id=approver_handle,
                ),
                now=now,
            )

        self._emit_event(
            request_id=request_id, actor=requester, source=source,
            event_type=AuditEventType.REQUEST_SUBMITTED, actor_kind=ActorKind.REQUESTER,
            revision=1, summary="Request submitted",
            payload={
                "target_label": change.target_label,
                "change_from_summary": change.change_from_summary,
                "change_to_summary": change.change_to_summary,
                "approver_handle": approver_handle,
            },
        )
        if approver_handle:
            self._emit_event(
                request_id=request_id, actor=requester, source=source,
                event_type=AuditEventType.APPROVER_NOTIFIED, actor_kind=ActorKind.AGENT,
                revision=1, summary="Approver notification queued",
                payload={"approver_handle": approver_handle},
            )
        return record

    def request_more_info(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        note: str,
        source: MessageSource,
    ) -> RequestRecord:
        record = self._change_status(
            request_id=request_id,
            to_status=ReviewStatus.NEEDS_INFO,
            actor=actor,
            note=note,
        )
        self._emit_event(
            request_id=request_id, actor=actor, source=source,
            event_type=AuditEventType.NEEDS_INFO_REQUESTED, actor_kind=ActorKind.APPROVER,
            revision=record.last_submitted_revision, summary="Approver requested more information",
            payload={"note": note},
        )
        return record

    def resubmit_request(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        change: ChangeRequest,
        source: MessageSource,
    ) -> RequestRecord:
        record = self.get_request(request_id)
        validate_transition(record.review_status, ReviewStatus.SUBMITTED)

        now = utc_now()
        record.review_status = ReviewStatus.SUBMITTED
        record.current_revision += 1
        record.last_submitted_revision = record.current_revision
        record.last_submitted_at = now
        record.updated_at = now
        record.target_label = change.target_label
        record.change_from_summary = change.change_from_summary
        record.change_to_summary = change.change_to_summary
        record.business_reason = change.business_reason
        record.request_text = change.request_text
        record.structured_payload_json = change.structured_payload_json
        self._workflow_store.update_request(record)

        self._emit_event(
            request_id=request_id, actor=actor, source=source,
            event_type=AuditEventType.REQUEST_RESUBMITTED, actor_kind=ActorKind.REQUESTER,
            revision=record.last_submitted_revision, summary="Requester resubmitted the request",
            payload={
                "target_label": change.target_label,
                "change_from_summary": change.change_from_summary,
                "change_to_summary": change.change_to_summary,
                "business_reason": change.business_reason,
            },
        )
        return record

    def approve_request(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        note: str | None,
        source: MessageSource,
    ) -> RequestRecord:
        record = self._change_status(
            request_id=request_id,
            to_status=ReviewStatus.APPROVED,
            actor=actor,
            note=note,
        )
        self._emit_event(
            request_id=request_id, actor=actor, source=source,
            event_type=AuditEventType.DECISION_RECORDED, actor_kind=ActorKind.APPROVER,
            revision=record.last_submitted_revision, summary="Approver approved the request",
            payload={"decision": "approved", "note": note},
        )
        return record

    def reject_request(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        note: str,
        source: MessageSource,
    ) -> RequestRecord:
        if self._config.workflow.reject_requires_reason and not note.strip():
            raise ValueError("Rejection reason is required")

        record = self._change_status(
            request_id=request_id,
            to_status=ReviewStatus.REJECTED,
            actor=actor,
            note=note,
        )
        self._emit_event(
            request_id=request_id, actor=actor, source=source,
            event_type=AuditEventType.DECISION_RECORDED, actor_kind=ActorKind.APPROVER,
            revision=record.last_submitted_revision, summary="Approver rejected the request",
            payload={"decision": "rejected", "note": note},
        )
        return record

    def cancel_request(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        note: str | None,
        source: MessageSource,
    ) -> RequestRecord:
        record = self._change_status(
            request_id=request_id,
            to_status=ReviewStatus.CANCELLED,
            actor=actor,
            note=note,
        )
        self._emit_event(
            request_id=request_id, actor=actor, source=source,
            event_type=AuditEventType.REQUEST_CANCELLED, actor_kind=ActorKind.REQUESTER,
            revision=record.last_submitted_revision, summary="Request was cancelled",
            payload={"note": note},
        )
        return record

    def get_request(self, request_id: str) -> RequestRecord:
        # Try exact match first, then uppercase-normalized (IDs are stored uppercase)
        record = self._workflow_store.get_request(request_id)
        if record is None:
            record = self._workflow_store.get_request(request_id.upper())
        if record is None:
            raise RequestNotFoundError(f"Request {request_id} was not found")
        return record

    def get_request_summary(self, request_id: str) -> RequestSummary:
        record = self.get_request(request_id)
        return self._to_request_summary(record)

    def list_request_summaries(
        self,
        *,
        requester_handle: str | None = None,
        approver_handle: str | None = None,
        review_statuses: set[ReviewStatus] | None = None,
    ) -> list[RequestSummary]:
        records = self._workflow_store.list_requests()
        filtered: list[RequestRecord] = []
        for record in records:
            if requester_handle and record.requester_handle != requester_handle:
                continue
            if approver_handle and record.approver_handle != approver_handle:
                continue
            if review_statuses and record.review_status not in review_statuses:
                continue
            filtered.append(record)

        filtered.sort(key=lambda record: record.updated_at, reverse=True)
        return [self._to_request_summary(record) for record in filtered]

    def search_by_target_label(self, query: str) -> list[RequestSummary]:
        q = query.strip().lower()
        if not q:
            return []
        records = self._workflow_store.list_requests()
        scored: list[tuple[float, RequestRecord]] = []
        for record in records:
            ts = target_match_score(q, record.target_label.lower())
            id_score = target_match_score(q, record.request_id.lower())
            score = max(ts, id_score)
            if score > 0:
                scored.append((score, record))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [self._to_request_summary(r) for _, r in scored]

    def list_requester_pending_summaries(self, requester_handle: str) -> list[RequestSummary]:
        return self.list_request_summaries(
            requester_handle=requester_handle,
            review_statuses={
                ReviewStatus.SUBMITTED,
                ReviewStatus.NEEDS_INFO,
                ReviewStatus.IN_REVIEW,
            },
        )

    def list_approver_pending_summaries(self, approver_handle: str) -> list[RequestSummary]:
        return self.list_request_summaries(
            approver_handle=approver_handle,
            review_statuses={
                ReviewStatus.SUBMITTED,
                ReviewStatus.IN_REVIEW,
            },
        )

    def _emit_event(
        self,
        *,
        request_id: str,
        actor: ActorContext,
        source: MessageSource,
        event_type: AuditEventType,
        actor_kind: ActorKind,
        revision: int | None,
        summary: str,
        payload: EventPayload,
    ) -> None:
        self._audit_service.record_event(
            request_id=request_id,
            actor=actor,
            event=AuditEventInput(
                event_type=event_type,
                actor_kind=actor_kind,
                request_revision=revision,
                summary=summary,
                event_payload=payload,
                source=source,
            ),
        )

    def _change_status(
        self,
        *,
        request_id: str,
        to_status: ReviewStatus,
        actor: ActorContext,
        note: str | None,
    ) -> RequestRecord:
        record = self.get_request(request_id)
        validate_transition(record.review_status, to_status)
        now = utc_now()
        record.review_status = to_status
        record.updated_at = now

        if to_status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
            record.resolved_at = now
            record.resolution_note = note
            record.resolved_by_name = actor.name or None  # empty string → None for storage
            record.resolved_by_handle = actor.handle

        if to_status == ReviewStatus.CANCELLED:
            record.cancelled_at = now
            record.cancelled_by_handle = actor.handle
            record.cancellation_note = note

        self._workflow_store.update_request(record)
        return record

    def _link_conversation(
        self,
        *,
        request_id: str,
        actor_handle: str,
        role: ConversationRole,
        source: MessageSource,
        now: datetime,
    ) -> None:
        self._workflow_store.create_request_conversation(
            RequestConversationRecord(
                request_id=request_id,
                actor_handle=actor_handle,
                conversation_role=role,
                channel_id=source.channel_id,
                thread_id=source.thread_id,
                conversation_id=source.channel_id,
                linked_at=now,
                last_seen_at=now,
            )
        )

    def _generate_request_id(self) -> str:
        suffix = uuid4().hex[:8].upper()
        return f"{self._config.app.request_id_prefix}-{suffix}"

    def _to_request_summary(self, record: RequestRecord) -> RequestSummary:
        structured_payload = None
        if record.structured_payload_json:
            try:
                loaded = json.loads(record.structured_payload_json)
                if isinstance(loaded, dict):
                    structured_payload = loaded
            except json.JSONDecodeError:
                structured_payload = None

        return RequestSummary(
            request_id=record.request_id,
            requester_handle=record.requester_handle,
            approver_handle=record.approver_handle,
            target_label=record.target_label,
            change_from_summary=record.change_from_summary,
            change_to_summary=record.change_to_summary,
            review_status=record.review_status.value,
            current_revision=record.current_revision,
            last_submitted_revision=record.last_submitted_revision,
            updated_at=record.updated_at.isoformat(),
            created_at=record.created_at.isoformat(),
            request_text=record.request_text,
            structured_payload_json=record.structured_payload_json,
            structured_payload=structured_payload,
        )
