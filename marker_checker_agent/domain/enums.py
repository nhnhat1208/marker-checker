from enum import StrEnum


class ReviewStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    NEEDS_INFO = "needs_info"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AuditEventType(StrEnum):
    REQUEST_SUBMITTED = "request_submitted"
    MISSING_FIELDS_REQUESTED = "missing_fields_requested"
    REQUEST_DRAFT_UPDATED = "request_draft_updated"
    APPROVER_NOTIFIED = "approver_notified"
    NEEDS_INFO_REQUESTED = "needs_info_requested"
    REQUEST_RESUBMITTED = "request_resubmitted"
    DECISION_RECORDED = "decision_recorded"
    REQUEST_CANCELLED = "request_cancelled"
    LOOKUP_PERFORMED = "lookup_performed"


class Operation(StrEnum):
    # Approver actions
    APPROVE = "approve"
    REJECT = "reject"
    NEEDINFO = "needinfo"
    CANCEL = "cancel"
    # Requester management operations
    LOOKUP = "lookup"
    HISTORY = "history"
    RESUBMIT = "resubmit"
    MY_PENDING = "my_pending"
    PENDING_APPROVALS = "pending_approvals"
    CONFIRM = "confirm"
    SEARCH = "search"
    # Intent classification sentinels
    NEW_REQUEST = "new_request"
    UNKNOWN = "unknown"


class ActorKind(StrEnum):
    USER = "user"
    SYSTEM = "system"
    REQUESTER = "requester"
    APPROVER = "approver"
    AGENT = "agent"
    LOOKUP_USER = "lookup_user"


class ConversationRole(StrEnum):
    REQUESTER_FOLLOWUP = "requester_followup"
    APPROVER_REVIEW = "approver_review"
    NONE = ""


class ResponseStatus(StrEnum):
    OK = "ok"
    ERROR = "error"
    SUBMITTED = "submitted"
    MISSING_FIELDS = "missing_fields"
    CONFIRMATION_REQUIRED = "confirmation_required"
    NEEDS_INPUT = "needs_input"
