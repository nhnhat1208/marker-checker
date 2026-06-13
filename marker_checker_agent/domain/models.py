from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, TypedDict

from marker_checker_agent.time_utils import utc_now


class RequestSummary(TypedDict):
    request_id: str
    requester_handle: str
    approver_handle: str
    target_label: str
    change_from_summary: str
    change_to_summary: str
    review_status: str
    current_revision: int
    last_submitted_revision: int
    updated_at: str


@dataclass(slots=True)
class RequestRecord:
    request_id: str
    request_text: str = ""
    requester_name: str | None = None
    requester_handle: str = ""
    approver_name: str | None = None
    approver_handle: str = ""
    target_label: str = ""
    target_object_type: str | None = None
    change_from_summary: str = ""
    change_to_summary: str = ""
    business_reason: str | None = None
    review_status: str = ""
    current_revision: int = 1
    last_submitted_revision: int = 1
    last_submitted_at: datetime = field(default_factory=utc_now)
    created_at: datetime = field(default_factory=utc_now)
    updated_at: datetime = field(default_factory=utc_now)
    resolved_at: datetime | None = None
    resolution_note: str | None = None
    resolved_by_name: str | None = None
    resolved_by_handle: str | None = None
    cancelled_at: datetime | None = None
    cancelled_by_handle: str | None = None
    cancellation_note: str | None = None
    origin_channel_id: str | None = None
    origin_thread_id: str | None = None
    origin_message_id: str | None = None


@dataclass(slots=True)
class AuditEventRecord:
    event_id: str = ""
    event_sequence: int = 0
    request_id: str = ""
    event_type: str = ""
    actor_name: str | None = None
    actor_handle: str = ""
    actor_kind: str = "user"
    request_revision: int | None = None
    occurred_at: datetime = field(default_factory=utc_now)
    summary: str = ""
    event_payload: dict[str, Any] = field(default_factory=dict)
    source_channel: str = "telegram"
    thread_id: str | None = None
    source_message_id: str | None = None


@dataclass(slots=True)
class RequestConversationRecord:
    row_id: str = ""
    request_id: str = ""
    actor_handle: str = ""
    conversation_role: str = ""
    channel_id: str | None = None
    thread_id: str | None = None
    conversation_id: str | None = None
    linked_at: datetime = field(default_factory=utc_now)
    last_seen_at: datetime = field(default_factory=utc_now)
