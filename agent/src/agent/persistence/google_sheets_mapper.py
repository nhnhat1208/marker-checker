from __future__ import annotations

import json
from datetime import datetime
from typing import TYPE_CHECKING, cast

from agent.domain.models import (
    AuditEventRecord,
    RequestConversationRecord,
    RequestRecord,
)
from agent.utils.time_utils import utc_now

if TYPE_CHECKING:
    from agent.domain.enums import ActorKind, AuditEventType, ReviewStatus

REQUEST_HEADERS = [
    "request_id",
    "request_text",
    "structured_payload_json",
    "impact_note",
    "requester_name",
    "requester_handle",
    "approver_name",
    "approver_handle",
    "target_label",
    "target_object_type",
    "change_from_summary",
    "change_to_summary",
    "business_reason",
    "review_status",
    "current_revision",
    "last_submitted_revision",
    "last_submitted_at",
    "created_at",
    "updated_at",
    "resolved_at",
    "resolution_note",
    "resolved_by_name",
    "resolved_by_handle",
    "cancelled_at",
    "cancelled_by_handle",
    "cancellation_note",
    "origin_channel_id",
    "origin_thread_id",
    "origin_message_id",
]

AUDIT_HEADERS = [
    "event_id",
    "event_sequence",
    "request_id",
    "event_type",
    "actor_name",
    "actor_handle",
    "actor_kind",
    "request_revision",
    "occurred_at",
    "summary",
    "event_payload",
    "source_channel",
    "thread_id",
    "source_message_id",
]

CONVERSATION_HEADERS = [
    "row_id",
    "request_id",
    "actor_handle",
    "conversation_role",
    "channel_id",
    "thread_id",
    "conversation_id",
    "linked_at",
    "last_seen_at",
]


def request_to_row(request: RequestRecord) -> list[str]:
    return [
        request.request_id,
        request.request_text,
        request.structured_payload_json or "",
        request.impact_note or "",
        request.requester_name or "",
        request.requester_handle,
        request.approver_name or "",
        request.approver_handle,
        request.target_label,
        request.target_object_type or "",
        request.change_from_summary,
        request.change_to_summary,
        request.business_reason or "",
        request.review_status,
        str(request.current_revision),
        str(request.last_submitted_revision),
        datetime_to_text(request.last_submitted_at),
        datetime_to_text(request.created_at),
        datetime_to_text(request.updated_at),
        datetime_to_text(request.resolved_at),
        request.resolution_note or "",
        request.resolved_by_name or "",
        request.resolved_by_handle or "",
        datetime_to_text(request.cancelled_at),
        request.cancelled_by_handle or "",
        request.cancellation_note or "",
        request.origin_channel_id or "",
        request.origin_thread_id or "",
        request.origin_message_id or "",
    ]


def request_from_row(row: dict[str, str]) -> RequestRecord:
    return RequestRecord(
        request_id=row.get("request_id", ""),
        request_text=row.get("request_text", ""),
        structured_payload_json=optional_text(row.get("structured_payload_json")),
        impact_note=optional_text(row.get("impact_note")),
        requester_name=optional_text(row.get("requester_name")),
        requester_handle=row.get("requester_handle", ""),
        approver_name=optional_text(row.get("approver_name")),
        approver_handle=row.get("approver_handle", ""),
        target_label=row.get("target_label", ""),
        target_object_type=optional_text(row.get("target_object_type")),
        change_from_summary=row.get("change_from_summary", ""),
        change_to_summary=row.get("change_to_summary", ""),
        business_reason=optional_text(row.get("business_reason")),
        review_status=cast("ReviewStatus", row.get("review_status", "")),
        current_revision=parse_int(row.get("current_revision")) or 1,
        last_submitted_revision=parse_int(row.get("last_submitted_revision")) or 1,
        last_submitted_at=parse_datetime(row.get("last_submitted_at")) or utc_now(),
        created_at=parse_datetime(row.get("created_at")) or utc_now(),
        updated_at=parse_datetime(row.get("updated_at")) or utc_now(),
        resolved_at=parse_datetime(row.get("resolved_at")),
        resolution_note=optional_text(row.get("resolution_note")),
        resolved_by_name=optional_text(row.get("resolved_by_name")),
        resolved_by_handle=optional_text(row.get("resolved_by_handle")),
        cancelled_at=parse_datetime(row.get("cancelled_at")),
        cancelled_by_handle=optional_text(row.get("cancelled_by_handle")),
        cancellation_note=optional_text(row.get("cancellation_note")),
        origin_channel_id=optional_text(row.get("origin_channel_id")),
        origin_thread_id=optional_text(row.get("origin_thread_id")),
        origin_message_id=optional_text(row.get("origin_message_id")),
    )


def audit_to_row(event: AuditEventRecord) -> list[str]:
    return [
        event.event_id,
        str(event.event_sequence),
        event.request_id,
        event.event_type,
        event.actor_name or "",
        event.actor_handle,
        event.actor_kind,
        str(event.request_revision) if event.request_revision is not None else "",
        datetime_to_text(event.occurred_at),
        event.summary,
        json.dumps(event.event_payload, separators=(",", ":"), ensure_ascii=True),
        event.source_channel,
        event.thread_id or "",
        event.source_message_id or "",
    ]


def audit_from_row(row: dict[str, str]) -> AuditEventRecord:
    payload = row.get("event_payload", "")
    return AuditEventRecord(
        event_id=row.get("event_id", ""),
        event_sequence=parse_int(row.get("event_sequence")) or 0,
        request_id=row.get("request_id", ""),
        event_type=cast("AuditEventType", row.get("event_type", "")),
        actor_name=optional_text(row.get("actor_name")),
        actor_handle=row.get("actor_handle", ""),
        actor_kind=cast("ActorKind", row.get("actor_kind", "user")),
        request_revision=parse_int(row.get("request_revision")),
        occurred_at=parse_datetime(row.get("occurred_at")) or utc_now(),
        summary=row.get("summary", ""),
        event_payload=json.loads(payload) if payload else {},
        source_channel=row.get("source_channel", "telegram"),
        thread_id=optional_text(row.get("thread_id")),
        source_message_id=optional_text(row.get("source_message_id")),
    )


def conversation_to_row(conversation: RequestConversationRecord) -> list[str]:
    return [
        conversation.row_id,
        conversation.request_id,
        conversation.actor_handle,
        conversation.conversation_role,
        conversation.channel_id or "",
        conversation.thread_id or "",
        conversation.conversation_id or "",
        datetime_to_text(conversation.linked_at),
        datetime_to_text(conversation.last_seen_at),
    ]


CHAT_REGISTRY_HEADERS = ["handle", "chat_id", "updated_at"]

PENDING_DRAFT_HEADERS = [
    "handle", "request_text", "requester_json", "parsed_json",
    "business_reason", "source_json", "expires_at",
]

PENDING_RESUBMIT_HEADERS = ["handle", "request_id", "expires_at"]


def optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value)


def parse_int(value: str | None) -> int | None:
    if not value:
        return None
    return int(value)


def datetime_to_text(value: datetime | None) -> str:
    if value is None:
        return ""
    return value.isoformat()
