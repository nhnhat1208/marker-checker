from __future__ import annotations

import re
from dataclasses import dataclass

from agent.utils.approver_handles import normalize_approver_handle


@dataclass(frozen=True, slots=True)
class ParsedRequest:
    target_label: str
    change_from_summary: str
    change_to_summary: str
    approver_handle: str


_APPROVER_PATTERN = (
    r"(?:"
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
    r"|[@#][A-Za-z0-9_]+"
    r")"
)

REQUEST_PATTERN = re.compile(
    r"(?:(?:for|on)\s+(?P<target>.+?)\s*,\s*)?"
    r"change\s+from\s+(?P<from>.+?)\s+to\s+(?P<to>.+?)\s*,?\s*"
    rf"(?:ask\s+(?P<approver_ask>{_APPROVER_PATTERN})\s+to\s+approve"
    rf"|(?P<approver_review>{_APPROVER_PATTERN})\s+should\s+(?:review|approve))",
    re.IGNORECASE,
)


def parse_request_text(text: str) -> ParsedRequest | None:
    match = REQUEST_PATTERN.search(text)
    if not match:
        return None

    approver = next(
        (
            group.strip()
            for group in (
                match.group("approver_ask"),
                match.group("approver_review"),
            )
            if group
        ),
        "",
    )
    return ParsedRequest(
        target_label=(match.group("target") or "").strip(),
        change_from_summary=match.group("from").strip(),
        change_to_summary=match.group("to").strip(),
        approver_handle=normalize_approver_handle(approver),
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
