from __future__ import annotations

import re
from dataclasses import dataclass

from marker_checker_agent.domain.enums import Operation


@dataclass(frozen=True)
class RoutedIntent:
    operation: Operation
    request_id: str
    note: str = ""
    text: str = ""
    target_name: str = ""


class FreeformIntentRouter:
    # Requires at least one digit in the final segment — matches REQ-A3F2C891
    # but not plain hyphenated words like api-gateway or nginx-config.
    _REQUEST_ID_PATTERN = r"(?P<request_id>[A-Za-z][A-Za-z0-9]*(?:-[A-Za-z0-9]+)*-[A-Za-z0-9]*\d[A-Za-z0-9]*)"
    _LOOKUP_PATTERN = re.compile(
        rf"^(?:(?:/)?status|lookup|check|show|show\s+request)\s+{_REQUEST_ID_PATTERN}\s*$",
        re.IGNORECASE,
    )
    _HISTORY_PATTERN = re.compile(
        rf"^(?:(?:/)?history|timeline|show\s+history)\s+{_REQUEST_ID_PATTERN}\s*$",
        re.IGNORECASE,
    )
    _CANCEL_PATTERN = re.compile(
        rf"^(?:(?:/)?cancel|cancel\s+request)\s+{_REQUEST_ID_PATTERN}(?:\s+(?P<note>.+))?\s*$",
        re.IGNORECASE,
    )
    _NEEDINFO_PATTERN = re.compile(
        rf"^(?:(?:/)?needinfo|need\s+info|need\s+more\s+info|ask\s+for\s+more\s+info)\s+{_REQUEST_ID_PATTERN}(?:\s+(?P<note>.+))?\s*$",
        re.IGNORECASE,
    )
    _RESUBMIT_PATTERN = re.compile(
        rf"^(?:(?:/)?resubmit)\s+{_REQUEST_ID_PATTERN}\s+(?P<text>.+)\s*$",
        re.IGNORECASE,
    )
    _MY_PENDING_PATTERN = re.compile(
        r"^(?:my\s+(?:pending|open)\s+requests|my\s+requests|requests\s+for\s+me"
        r"|(?:list|show)(?:\s+my)?\s+requests?)\s*$",
        re.IGNORECASE,
    )
    _PENDING_APPROVALS_PATTERN = re.compile(
        r"^(?:what\s+needs\s+approval|pending\s+approvals|my\s+approvals"
        r"|what\s+should\s+i\s+approve|requests\s+to\s+approve|can\s+i\s+approve\s+something)\s*$",
        re.IGNORECASE,
    )

    def route(self, text: str) -> RoutedIntent | None:
        lookup_match = self._LOOKUP_PATTERN.match(text)
        if lookup_match:
            return RoutedIntent(
                operation=Operation.LOOKUP,
                request_id=lookup_match.group("request_id"),
            )

        history_match = self._HISTORY_PATTERN.match(text)
        if history_match:
            return RoutedIntent(
                operation=Operation.HISTORY,
                request_id=history_match.group("request_id"),
            )

        cancel_match = self._CANCEL_PATTERN.match(text)
        if cancel_match:
            return RoutedIntent(
                operation=Operation.CANCEL,
                request_id=cancel_match.group("request_id"),
                note=(cancel_match.group("note") or "").strip(),
            )

        needinfo_match = self._NEEDINFO_PATTERN.match(text)
        if needinfo_match:
            return RoutedIntent(
                operation=Operation.NEEDINFO,
                request_id=needinfo_match.group("request_id"),
                note=(needinfo_match.group("note") or "").strip(),
            )

        resubmit_match = self._RESUBMIT_PATTERN.match(text)
        if resubmit_match:
            return RoutedIntent(
                operation=Operation.RESUBMIT,
                request_id=resubmit_match.group("request_id"),
                text=resubmit_match.group("text").strip(),
            )

        if self._MY_PENDING_PATTERN.match(text):
            return RoutedIntent(operation=Operation.MY_PENDING, request_id="")

        if self._PENDING_APPROVALS_PATTERN.match(text):
            return RoutedIntent(operation=Operation.PENDING_APPROVALS, request_id="")

        return None
