from enum import Enum


class ReviewStatus(str, Enum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    IN_REVIEW = "in_review"
    NEEDS_INFO = "needs_info"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"


class AuditEventType(str, Enum):
    REQUEST_SUBMITTED = "request_submitted"
    MISSING_FIELDS_REQUESTED = "missing_fields_requested"
    REQUEST_DRAFT_UPDATED = "request_draft_updated"
    APPROVER_NOTIFIED = "approver_notified"
    NEEDS_INFO_REQUESTED = "needs_info_requested"
    REQUEST_RESUBMITTED = "request_resubmitted"
    DECISION_RECORDED = "decision_recorded"
    REQUEST_CANCELLED = "request_cancelled"
    LOOKUP_PERFORMED = "lookup_performed"
