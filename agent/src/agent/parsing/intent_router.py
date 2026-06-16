from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent.domain.enums import Operation

if TYPE_CHECKING:
    from collections.abc import Callable
    from typing import ClassVar


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
        rf"^(?:(?:/)?status|lookup|check|show|show\s+request|detail|details|detial"
        rf"|detail\s+(?:for|of)?\s*request|detial\s+(?:for|of)?\s*request)\s+{_REQUEST_ID_PATTERN}\s*$",
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
        r"|(?:list|show)(?:\s+my)?\s+requests?"
        r"|show\s+(?:my\s+)?last\s+request|last\s+request)\s*$",
        re.IGNORECASE,
    )
    _PENDING_APPROVALS_PATTERN = re.compile(
        r"^(?:what\s+needs\s+approval|pending\s+approvals|my\s+approvals"
        r"|what\s+should\s+i\s+approve|requests\s+to\s+approve|can\s+i\s+approve\s+something"
        r"|list\s+(?:my\s+)?approvals|show\s+(?:my\s+)?approvals)\s*$",
        re.IGNORECASE,
    )
    # "search nginx" / "find requests for nginx" / "show request merchant reconcile"
    # Placed after _LOOKUP_PATTERN so "show request REQ-XXXX" is caught as LOOKUP first.
    _SEARCH_PATTERN = re.compile(
        r"^(?:(?:/)?search|find\s+requests?\s+for|show\s+request)\s+(?P<target>.+?)\s*$",
        re.IGNORECASE,
    )

    _MATCHERS: ClassVar[list[tuple[re.Pattern[str], Callable[[re.Match[str]], RoutedIntent]]]] = [
        (_LOOKUP_PATTERN,
         lambda m: RoutedIntent(operation=Operation.LOOKUP, request_id=m.group("request_id"))),
        (_HISTORY_PATTERN,
         lambda m: RoutedIntent(operation=Operation.HISTORY, request_id=m.group("request_id"))),
        (_CANCEL_PATTERN,
         lambda m: RoutedIntent(
             operation=Operation.CANCEL, request_id=m.group("request_id"),
             note=(m.group("note") or "").strip(),
         )),
        (_NEEDINFO_PATTERN,
         lambda m: RoutedIntent(
             operation=Operation.NEEDINFO, request_id=m.group("request_id"),
             note=(m.group("note") or "").strip(),
         )),
        (_RESUBMIT_PATTERN,
         lambda m: RoutedIntent(
             operation=Operation.RESUBMIT, request_id=m.group("request_id"),
             text=m.group("text").strip(),
         )),
        (_MY_PENDING_PATTERN,
         lambda _: RoutedIntent(operation=Operation.MY_PENDING, request_id="")),
        (_PENDING_APPROVALS_PATTERN,
         lambda _: RoutedIntent(operation=Operation.PENDING_APPROVALS, request_id="")),
        (_SEARCH_PATTERN,
         lambda m: RoutedIntent(
             operation=Operation.SEARCH, request_id="", target_name=m.group("target").strip(),
         )),
    ]

    def route(self, text: str) -> RoutedIntent | None:
        for pattern, builder in self._MATCHERS:
            m = pattern.match(text)
            if m:
                return builder(m)
        return None
