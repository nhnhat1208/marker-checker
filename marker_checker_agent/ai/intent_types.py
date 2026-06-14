from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from marker_checker_agent.domain.enums import Operation

if TYPE_CHECKING:
    from marker_checker_agent.parsing.request_parser import ParsedRequest

MANAGEMENT_OPERATIONS: frozenset[Operation] = frozenset({
    Operation.LOOKUP,
    Operation.HISTORY,
    Operation.CANCEL,
    Operation.NEEDINFO,
    Operation.RESUBMIT,
    Operation.MY_PENDING,
    Operation.PENDING_APPROVALS,
    Operation.CONFIRM,
    Operation.SEARCH,
})


@dataclass(frozen=True, slots=True)
class IntentManagement:
    operation: Operation
    request_id: str = ""
    target_name: str = ""
    note: str = ""
    text: str = ""


@dataclass(frozen=True, slots=True)
class IntentNewRequest:
    target_label: str = ""
    change_from_summary: str = ""
    change_to_summary: str = ""
    approver_handle: str = ""
    guidance_message: str | None = None


@dataclass(frozen=True, slots=True)
class IntentUnknown:
    pass


IntentResult = IntentManagement | IntentNewRequest | IntentUnknown


@dataclass(frozen=True, slots=True)
class AssistedParseResult:
    parsed_request: ParsedRequest | None
    guidance_message: str | None = None
    parser_name: str = "pattern"
    missing_fields: list[str] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    latency_ms: int | None = None
    model: str | None = None
    prompt_version: str | None = None
