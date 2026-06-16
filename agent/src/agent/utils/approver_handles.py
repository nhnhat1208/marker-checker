from __future__ import annotations

import re

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$"
)
MENTION_PATTERN = re.compile(r"^@[\w][\w.-]*$")


def is_email_approver(value: str) -> bool:
    return bool(EMAIL_PATTERN.match(value.strip()))


def is_valid_approver_handle(value: str) -> bool:
    normalized = value.strip()
    return bool(normalized) and (
        is_email_approver(normalized) or bool(MENTION_PATTERN.match(normalized))
    )


def normalize_approver_handle(value: str) -> str:
    normalized = value.strip().strip(",.;")
    if not normalized:
        return ""
    if is_email_approver(normalized):
        return normalized.casefold()
    if normalized.startswith("#"):
        normalized = normalized[1:].strip()
    if normalized.startswith("@"):
        return f"@{normalized[1:].strip()}"
    return f"@{normalized}"
