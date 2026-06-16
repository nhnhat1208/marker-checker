from __future__ import annotations

import json
from datetime import datetime
from enum import StrEnum
from typing import TypedDict, TypeVar

from pydantic import BaseModel, Field, field_serializer, field_validator

from agent.domain.enums import (
    ActorKind,
    AuditEventType,
    ConversationRole,
    Operation,
    ReviewStatus,
)
from agent.utils.time_utils import utc_now


class ActorContext(BaseModel):
    """Identity of the actor performing an operation."""
    name: str = ""
    handle: str


class MessageSource(BaseModel):
    """Channel and message metadata for an inbound message."""
    source_channel: str = "telegram"
    channel_id: str | None = None
    thread_id: str | None = None
    source_message_id: str | None = None


class CodeFormat(StrEnum):
    """Format of a code section or request body."""

    TEXT = "text"
    YAML = "yaml"
    JSON = "json"


class RequestMode(StrEnum):
    """How the change request is structured."""

    FREE_TEXT = "free_text"
    CONFIG_CHANGE = "config_change"
    OBJECT_CHANGE = "object_change"


class StructuredCodeSection(TypedDict):
    enabled: bool
    format: CodeFormat
    value: str


class StructuredRequestPayload(TypedDict):
    mode: RequestMode
    request_format: CodeFormat
    request: str
    approver: str
    before: StructuredCodeSection
    after: StructuredCodeSection


class _RequestSummaryRequired(TypedDict):
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
    created_at: str


class RequestSummary(_RequestSummaryRequired, total=False):
    request_text: str
    structured_payload_json: str | None
    structured_payload: StructuredRequestPayload | None
    impact_note: str | None


class TimelineEvent(TypedDict):
    event_sequence: int
    event_type: str
    summary: str
    actor_handle: str
    occurred_at: str


class AssistantMetadata(TypedDict):
    model: str | None
    prompt_version: str | None
    latency_ms: int | None
    validation_errors: list[str]


class DraftPreview(TypedDict):
    requester_handle: str
    approver_handle: str
    target_label: str
    change_from_summary: str
    change_to_summary: str
    parser: str
    parser_metadata: AssistantMetadata | None


class _CoordinatorResponseRequired(TypedDict):
    status: str


class UiResponseRequest(TypedDict, total=False):
    request_id: str
    requester_handle: str
    approver_handle: str
    target_label: str
    change_from_summary: str
    change_to_summary: str
    review_status: str
    request_text: str
    structured_payload: StructuredRequestPayload | None
    impact_note: str | None


class UiResponseDraft(TypedDict, total=False):
    requester_handle: str
    approver_handle: str
    target_label: str
    change_from_summary: str
    change_to_summary: str
    parser: str


class UiResponse(TypedDict, total=False):
    kind: str
    title: str
    body: str
    status: str
    request: UiResponseRequest
    requests: list[UiResponseRequest]
    draft: UiResponseDraft
    impact_note: str | None


class CoordinatorResponse(_CoordinatorResponseRequired, total=False):
    message: str
    request: RequestSummary
    requests: list[RequestSummary]
    timeline: list[TimelineEvent]
    summary_message: str | None
    missing_fields: list[str]
    parser: str
    parser_metadata: AssistantMetadata | None
    draft: DraftPreview
    ui_response: UiResponse


class InvocationPayload(TypedDict, total=False):
    operation: str
    actor_name: str
    actor_handle: str
    source_channel: str
    channel_id: str
    thread_id: str
    source_message_id: str
    message: str
    request_id: str
    note: str
    target_name: str


# Flat key→scalar mapping stored as JSON in the audit event log
EventPayload = dict[str, str | None]


class ChangeRequest(BaseModel):
    """Bundles the change details for creating or resubmitting a request."""
    approver_handle: str
    target_label: str
    change_from_summary: str
    change_to_summary: str
    impact_note: str | None = None
    request_text: str = ""
    business_reason: str | None = None
    structured_payload_json: str | None = None


class WorkflowAction(BaseModel):
    """Bundles an approver action with its target request and optional note."""
    action: Operation
    request_id: str
    note: str = ""


class AuditEventInput(BaseModel):
    """Input bundle for recording an audit event."""
    event_type: AuditEventType
    actor_kind: ActorKind = ActorKind.USER
    request_revision: int | None = None
    summary: str = ""
    event_payload: EventPayload | None = None
    source: MessageSource | None = None


# ---------------------------------------------------------------------------
# Field coercion helpers (used by validators below)
# ---------------------------------------------------------------------------

_E = TypeVar("_E", bound=StrEnum)


def _coerce_enum(v: object, cls: type[_E], default: _E) -> _E:
    if isinstance(v, cls):
        return v
    try:
        return cls(str(v))
    except ValueError:
        return default


def _to_event_scalar(v: object) -> str | None:
    if v is None:
        return None
    if isinstance(v, str):
        return v
    return str(v)


def _opt_str(v: object) -> str | None:
    if isinstance(v, str):
        return v.strip() or None
    return None


def _opt_dt(v: object) -> datetime | None:
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, datetime):
        return v
    return datetime.fromisoformat(str(v))


def _req_dt(v: object) -> datetime:
    if isinstance(v, datetime):
        return v
    if isinstance(v, str) and v.strip():
        return datetime.fromisoformat(v)
    return utc_now()


def _rev_int(v: object, *, default: int = 1) -> int:
    if isinstance(v, int):
        return v
    if isinstance(v, str) and v.strip():
        return int(v)
    return default


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


class RequestRecord(BaseModel):
    request_id: str
    request_text: str = ""
    structured_payload_json: str | None = None
    impact_note: str | None = None
    requester_name: str | None = None
    requester_handle: str = ""
    approver_name: str | None = None
    approver_handle: str = ""
    target_label: str = ""
    target_object_type: str | None = None
    change_from_summary: str = ""
    change_to_summary: str = ""
    business_reason: str | None = None
    review_status: ReviewStatus = ReviewStatus.DRAFT
    current_revision: int = 1
    last_submitted_revision: int = 1
    last_submitted_at: datetime = Field(default_factory=utc_now)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
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

    @field_validator("review_status", mode="before")
    @classmethod
    def _parse_status(cls, v: object) -> ReviewStatus:
        return _coerce_enum(v, ReviewStatus, ReviewStatus.DRAFT)

    @field_validator(
        "structured_payload_json", "impact_note", "requester_name", "approver_name",
        "target_object_type", "business_reason",
        "resolution_note", "resolved_by_name", "resolved_by_handle",
        "cancelled_by_handle", "cancellation_note",
        "origin_channel_id", "origin_thread_id", "origin_message_id",
        mode="before",
    )
    @classmethod
    def _parse_opt_str(cls, v: object) -> str | None:
        return _opt_str(v)

    @field_validator("created_at", "updated_at", "last_submitted_at", mode="before")
    @classmethod
    def _parse_req_dt(cls, v: object) -> datetime:
        return _req_dt(v)

    @field_validator("resolved_at", "cancelled_at", mode="before")
    @classmethod
    def _parse_opt_dt(cls, v: object) -> datetime | None:
        return _opt_dt(v)

    @field_validator("current_revision", "last_submitted_revision", mode="before")
    @classmethod
    def _parse_revision(cls, v: object) -> int:
        return _rev_int(v, default=1)


class AuditEventRecord(BaseModel):
    event_id: str = ""
    event_sequence: int = 0
    request_id: str = ""
    event_type: AuditEventType = AuditEventType.LOOKUP_PERFORMED
    actor_name: str | None = None
    actor_handle: str = ""
    actor_kind: ActorKind = ActorKind.USER
    request_revision: int | None = None
    occurred_at: datetime = Field(default_factory=utc_now)
    summary: str = ""
    event_payload: EventPayload = Field(default_factory=dict)
    source_channel: str = "telegram"
    thread_id: str | None = None
    source_message_id: str | None = None

    @field_validator("event_type", mode="before")
    @classmethod
    def _parse_event_type(cls, v: object) -> AuditEventType:
        return _coerce_enum(v, AuditEventType, AuditEventType.LOOKUP_PERFORMED)

    @field_validator("actor_name", "thread_id", "source_message_id", mode="before")
    @classmethod
    def _parse_opt_str(cls, v: object) -> str | None:
        return _opt_str(v)

    @field_validator("actor_kind", mode="before")
    @classmethod
    def _parse_actor_kind(cls, v: object) -> ActorKind:
        return _coerce_enum(v, ActorKind, ActorKind.USER)

    @field_validator("source_channel", mode="before")
    @classmethod
    def _parse_source_channel(cls, v: object) -> str:
        return _opt_str(v) or "telegram"

    @field_validator("occurred_at", mode="before")
    @classmethod
    def _parse_occurred_at(cls, v: object) -> datetime:
        return _req_dt(v)

    @field_validator("event_payload", mode="before")
    @classmethod
    def _parse_event_payload(cls, v: object) -> EventPayload:
        if isinstance(v, dict):
            return {str(k): _to_event_scalar(val) for k, val in v.items()}
        if isinstance(v, str) and v.strip():
            loaded = json.loads(v)
            if isinstance(loaded, dict):
                return {str(k): _to_event_scalar(val) for k, val in loaded.items()}
        return {}

    @field_validator("event_sequence", mode="before")
    @classmethod
    def _parse_sequence(cls, v: object) -> int:
        return _rev_int(v, default=0)

    @field_validator("request_revision", mode="before")
    @classmethod
    def _parse_request_revision(cls, v: object) -> int | None:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        if isinstance(v, int):
            return v
        return int(str(v))

    @field_serializer("event_payload", when_used="json")
    def _serialize_event_payload(self, v: EventPayload) -> str:
        return json.dumps(v, separators=(",", ":"), ensure_ascii=True)


class RequestConversationRecord(BaseModel):
    row_id: str = ""
    request_id: str = ""
    actor_handle: str = ""
    conversation_role: ConversationRole = ConversationRole.NONE
    channel_id: str | None = None
    thread_id: str | None = None
    conversation_id: str | None = None
    linked_at: datetime = Field(default_factory=utc_now)
    last_seen_at: datetime = Field(default_factory=utc_now)

    @field_validator("channel_id", "thread_id", "conversation_id", mode="before")
    @classmethod
    def _parse_opt_str(cls, v: object) -> str | None:
        return _opt_str(v)

    @field_validator("conversation_role", mode="before")
    @classmethod
    def _parse_role(cls, v: object) -> ConversationRole:
        return _coerce_enum(v, ConversationRole, ConversationRole.NONE)

    @field_validator("linked_at", "last_seen_at", mode="before")
    @classmethod
    def _parse_dt(cls, v: object) -> datetime:
        return _req_dt(v)
