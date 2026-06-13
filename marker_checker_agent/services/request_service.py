from __future__ import annotations

from typing import Any
from uuid import uuid4

from marker_checker_agent.config import RuntimeConfig
from marker_checker_agent.domain.enums import AuditEventType, ReviewStatus
from marker_checker_agent.domain.models import RequestConversationRecord, RequestRecord
from marker_checker_agent.persistence.base import WorkflowStore
from marker_checker_agent.services.audit_service import AuditService
from marker_checker_agent.time_utils import utc_now


class InvalidTransitionError(ValueError):
    """Raised when a workflow transition is not allowed."""


class RequestNotFoundError(LookupError):
    """Raised when a request cannot be found."""


class RequestService:
    _allowed_transitions: dict[ReviewStatus, set[ReviewStatus]] = {
        ReviewStatus.SUBMITTED: {
            ReviewStatus.NEEDS_INFO,
            ReviewStatus.APPROVED,
            ReviewStatus.REJECTED,
            ReviewStatus.CANCELLED,
        },
        ReviewStatus.NEEDS_INFO: {
            ReviewStatus.SUBMITTED,
            ReviewStatus.CANCELLED,
        },
        ReviewStatus.APPROVED: set(),
        ReviewStatus.REJECTED: set(),
        ReviewStatus.CANCELLED: set(),
        ReviewStatus.DRAFT: {ReviewStatus.SUBMITTED},
        ReviewStatus.IN_REVIEW: {
            ReviewStatus.NEEDS_INFO,
            ReviewStatus.APPROVED,
            ReviewStatus.REJECTED,
            ReviewStatus.CANCELLED,
        },
    }

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
        request_text: str,
        requester_name: str | None,
        requester_handle: str,
        approver_name: str | None,
        approver_handle: str,
        target_label: str,
        change_from_summary: str,
        change_to_summary: str,
        business_reason: str | None,
        source_channel: str,
        channel_id: str | None,
        thread_id: str | None,
        source_message_id: str | None,
    ) -> RequestRecord:
        request_id = self._generate_request_id()
        now = utc_now()

        record = RequestRecord(
            request_id=request_id,
            request_text=request_text,
            requester_name=requester_name,
            requester_handle=requester_handle,
            approver_name=approver_name,
            approver_handle=approver_handle,
            target_label=target_label,
            change_from_summary=change_from_summary,
            change_to_summary=change_to_summary,
            business_reason=business_reason,
            review_status=ReviewStatus.SUBMITTED.value,
            current_revision=1,
            last_submitted_revision=1,
            last_submitted_at=now,
            created_at=now,
            updated_at=now,
            origin_channel_id=channel_id,
            origin_thread_id=thread_id,
            origin_message_id=source_message_id,
        )
        self._workflow_store.create_request(record)
        self._workflow_store.create_request_conversation(
            RequestConversationRecord(
                request_id=request_id,
                actor_handle=requester_handle,
                conversation_role="requester_followup",
                channel_id=channel_id,
                thread_id=thread_id,
                conversation_id=channel_id,
                linked_at=now,
                last_seen_at=now,
            )
        )
        self._workflow_store.create_request_conversation(
            RequestConversationRecord(
                request_id=request_id,
                actor_handle=approver_handle,
                conversation_role="approver_review",
                channel_id=channel_id,
                thread_id=thread_id,
                conversation_id=channel_id,
                linked_at=now,
                last_seen_at=now,
            )
        )

        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.REQUEST_SUBMITTED,
            actor_name=requester_name,
            actor_handle=requester_handle,
            actor_kind="requester",
            request_revision=1,
            summary="Request submitted",
            event_payload={
                "target_label": target_label,
                "change_from_summary": change_from_summary,
                "change_to_summary": change_to_summary,
                "approver_handle": approver_handle,
            },
            source_channel=source_channel,
            thread_id=thread_id,
            source_message_id=source_message_id,
        )
        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.APPROVER_NOTIFIED,
            actor_name=requester_name,
            actor_handle=requester_handle,
            actor_kind="agent",
            request_revision=1,
            summary="Approver notification queued",
            event_payload={"approver_handle": approver_handle},
            source_channel=source_channel,
            thread_id=thread_id,
            source_message_id=source_message_id,
        )
        return record

    def request_more_info(
        self,
        *,
        request_id: str,
        actor_name: str | None,
        actor_handle: str,
        note: str,
        source_channel: str,
        source_message_id: str | None,
    ) -> RequestRecord:
        record = self._change_status(
            request_id=request_id,
            from_statuses={ReviewStatus.SUBMITTED, ReviewStatus.IN_REVIEW},
            to_status=ReviewStatus.NEEDS_INFO,
            actor_name=actor_name,
            actor_handle=actor_handle,
            note=note,
        )
        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.NEEDS_INFO_REQUESTED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            actor_kind="approver",
            request_revision=record.last_submitted_revision,
            summary="Approver requested more information",
            event_payload={"note": note},
            source_channel=source_channel,
            source_message_id=source_message_id,
        )
        return record

    def resubmit_request(
        self,
        *,
        request_id: str,
        actor_name: str | None,
        actor_handle: str,
        target_label: str,
        change_from_summary: str,
        change_to_summary: str,
        business_reason: str | None,
        request_text: str,
        source_channel: str,
        source_message_id: str | None,
    ) -> RequestRecord:
        record = self.get_request(request_id)
        current_status = ReviewStatus(record.review_status)
        if current_status != ReviewStatus.NEEDS_INFO:
            raise InvalidTransitionError(
                f"Cannot resubmit request {request_id} from status {record.review_status}"
            )

        record.current_revision += 1
        record.last_submitted_revision = record.current_revision
        record.last_submitted_at = utc_now()
        record.updated_at = utc_now()
        record.target_label = target_label
        record.change_from_summary = change_from_summary
        record.change_to_summary = change_to_summary
        record.business_reason = business_reason
        record.request_text = request_text
        record.review_status = ReviewStatus.SUBMITTED.value
        self._workflow_store.update_request(record)

        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.REQUEST_RESUBMITTED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            actor_kind="requester",
            request_revision=record.last_submitted_revision,
            summary="Requester resubmitted the request",
            event_payload={
                "target_label": target_label,
                "change_from_summary": change_from_summary,
                "change_to_summary": change_to_summary,
                "business_reason": business_reason,
            },
            source_channel=source_channel,
            source_message_id=source_message_id,
        )
        return record

    def approve_request(
        self,
        *,
        request_id: str,
        actor_name: str | None,
        actor_handle: str,
        note: str | None,
        source_channel: str,
        source_message_id: str | None,
    ) -> RequestRecord:
        record = self._change_status(
            request_id=request_id,
            from_statuses={ReviewStatus.SUBMITTED, ReviewStatus.IN_REVIEW},
            to_status=ReviewStatus.APPROVED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            note=note,
        )
        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.DECISION_RECORDED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            actor_kind="approver",
            request_revision=record.last_submitted_revision,
            summary="Approver approved the request",
            event_payload={"decision": "approved", "note": note},
            source_channel=source_channel,
            source_message_id=source_message_id,
        )
        return record

    def reject_request(
        self,
        *,
        request_id: str,
        actor_name: str | None,
        actor_handle: str,
        reason: str,
        source_channel: str,
        source_message_id: str | None,
    ) -> RequestRecord:
        if self._config.workflow.reject_requires_reason and not reason.strip():
            raise ValueError("Rejection reason is required")

        record = self._change_status(
            request_id=request_id,
            from_statuses={ReviewStatus.SUBMITTED, ReviewStatus.IN_REVIEW},
            to_status=ReviewStatus.REJECTED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            note=reason,
        )
        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.DECISION_RECORDED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            actor_kind="approver",
            request_revision=record.last_submitted_revision,
            summary="Approver rejected the request",
            event_payload={"decision": "rejected", "reason": reason},
            source_channel=source_channel,
            source_message_id=source_message_id,
        )
        return record

    def cancel_request(
        self,
        *,
        request_id: str,
        actor_name: str | None,
        actor_handle: str,
        note: str | None,
        source_channel: str,
        source_message_id: str | None,
    ) -> RequestRecord:
        record = self._change_status(
            request_id=request_id,
            from_statuses={ReviewStatus.SUBMITTED, ReviewStatus.NEEDS_INFO, ReviewStatus.IN_REVIEW},
            to_status=ReviewStatus.CANCELLED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            note=note,
        )
        self._audit_service.record_event(
            request_id=request_id,
            event_type=AuditEventType.REQUEST_CANCELLED,
            actor_name=actor_name,
            actor_handle=actor_handle,
            actor_kind="requester",
            request_revision=record.last_submitted_revision,
            summary="Request was cancelled",
            event_payload={"note": note},
            source_channel=source_channel,
            source_message_id=source_message_id,
        )
        return record

    def get_request(self, request_id: str) -> RequestRecord:
        record = self._workflow_store.get_request(request_id)
        if record is None:
            raise RequestNotFoundError(f"Request {request_id} was not found")
        return record

    def get_request_summary(self, request_id: str) -> dict[str, Any]:
        record = self.get_request(request_id)
        return self._to_request_summary(record)

    def list_request_summaries(
        self,
        *,
        requester_handle: str | None = None,
        approver_handle: str | None = None,
        review_statuses: set[str] | None = None,
    ) -> list[dict[str, Any]]:
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

    def list_requester_pending_summaries(self, requester_handle: str) -> list[dict[str, Any]]:
        return self.list_request_summaries(
            requester_handle=requester_handle,
            review_statuses={
                ReviewStatus.SUBMITTED.value,
                ReviewStatus.NEEDS_INFO.value,
                ReviewStatus.IN_REVIEW.value,
            },
        )

    def list_approver_pending_summaries(self, approver_handle: str) -> list[dict[str, Any]]:
        return self.list_request_summaries(
            approver_handle=approver_handle,
            review_statuses={
                ReviewStatus.SUBMITTED.value,
                ReviewStatus.IN_REVIEW.value,
            },
        )

    def _change_status(
        self,
        *,
        request_id: str,
        from_statuses: set[ReviewStatus],
        to_status: ReviewStatus,
        actor_name: str | None,
        actor_handle: str,
        note: str | None,
    ) -> RequestRecord:
        record = self.get_request(request_id)
        current_status = ReviewStatus(record.review_status)
        if current_status not in from_statuses:
            raise InvalidTransitionError(
                f"Cannot move request {request_id} from {record.review_status} to {to_status.value}"
            )

        self._validate_transition(current_status, to_status)
        record.review_status = to_status.value
        record.updated_at = utc_now()

        if to_status in {ReviewStatus.APPROVED, ReviewStatus.REJECTED}:
            record.resolved_at = utc_now()
            record.resolution_note = note
            record.resolved_by_name = actor_name
            record.resolved_by_handle = actor_handle

        if to_status == ReviewStatus.CANCELLED:
            record.cancelled_at = utc_now()
            record.cancelled_by_handle = actor_handle
            record.cancellation_note = note

        self._workflow_store.update_request(record)
        return record

    def _validate_transition(self, current_status: ReviewStatus, to_status: ReviewStatus) -> None:
        allowed = self._allowed_transitions.get(current_status, set())
        if to_status not in allowed:
            raise InvalidTransitionError(
                f"Transition {current_status.value} -> {to_status.value} is not allowed"
            )

    def _generate_request_id(self) -> str:
        suffix = uuid4().hex[:8].upper()
        return f"{self._config.app.request_id_prefix}-{suffix}"

    def _to_request_summary(self, record: RequestRecord) -> dict[str, Any]:
        return {
            "request_id": record.request_id,
            "requester_handle": record.requester_handle,
            "approver_handle": record.approver_handle,
            "target_label": record.target_label,
            "change_from_summary": record.change_from_summary,
            "change_to_summary": record.change_to_summary,
            "review_status": record.review_status,
            "current_revision": record.current_revision,
            "last_submitted_revision": record.last_submitted_revision,
            "updated_at": record.updated_at.isoformat(),
        }
