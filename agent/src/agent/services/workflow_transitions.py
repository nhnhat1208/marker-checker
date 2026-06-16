from __future__ import annotations

from agent.domain.enums import ReviewStatus

_ALLOWED_TRANSITIONS: dict[ReviewStatus, set[ReviewStatus]] = {
    ReviewStatus.DRAFT: {ReviewStatus.SUBMITTED},
    ReviewStatus.SUBMITTED: {
        ReviewStatus.NEEDS_INFO,
        ReviewStatus.APPROVED,
        ReviewStatus.REJECTED,
        ReviewStatus.CANCELLED,
    },
    ReviewStatus.IN_REVIEW: {
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
}


class InvalidTransitionError(ValueError):
    """Raised when a workflow transition is not allowed."""


def validate_transition(from_status: ReviewStatus, to_status: ReviewStatus) -> None:
    allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise InvalidTransitionError(
            f"Transition {from_status.value} -> {to_status.value} is not allowed"
        )
