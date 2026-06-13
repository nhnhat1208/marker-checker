from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    target_label: str
    change_from_summary: str
    change_to_summary: str
    approver_handle: str


REQUEST_PATTERN = re.compile(
    r"(?:(?:for|on)\s+(?P<target>.+?)\s*,\s*)?"
    r"change\s+from\s+(?P<from>.+?)\s+to\s+(?P<to>.+?)\s*,?\s*"
    r"ask\s+(?P<approver>[@#][\w_]+)\s+to\s+approve",
    re.IGNORECASE,
)


def parse_request_text(text: str) -> ParsedRequest | None:
    match = REQUEST_PATTERN.search(text)
    if not match:
        return None

    return ParsedRequest(
        target_label=(match.group("target") or "").strip(),
        change_from_summary=match.group("from").strip(),
        change_to_summary=match.group("to").strip(),
        approver_handle=match.group("approver").strip(),
    )


def list_missing_required_fields(parsed_request: ParsedRequest) -> list[str]:
    field_map = {
        "target_label": parsed_request.target_label,
        "change_from_summary": parsed_request.change_from_summary,
        "change_to_summary": parsed_request.change_to_summary,
        "approver_handle": parsed_request.approver_handle,
    }
    return [name for name, value in field_map.items() if not value]


def format_confirmation_message(parsed_request: ParsedRequest) -> str:
    return (
        "Confirm request submission:\n"
        f"- target: {parsed_request.target_label}\n"
        f"- from: {parsed_request.change_from_summary}\n"
        f"- to: {parsed_request.change_to_summary}\n"
        f"- approver: {parsed_request.approver_handle}\n\n"
        "Reply with /confirm to create the real request."
    )
