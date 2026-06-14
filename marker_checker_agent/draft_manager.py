from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cachetools import TTLCache

if TYPE_CHECKING:
    from marker_checker_agent.domain.models import ActorContext, MessageSource
    from marker_checker_agent.parsing.request_parser import ParsedRequest


@dataclass
class PendingDraft:
    request_text: str
    requester: ActorContext
    parsed_request: ParsedRequest
    business_reason: str | None
    source: MessageSource


class DraftManager:
    """Thread-safe store for per-user draft, resubmit, and partial-draft state."""

    def __init__(self) -> None:
        # TTLCache: maxsize caps memory, ttl prevents stale state after inactivity.
        # All three share _lock because TTLCache is not thread-safe.
        self._pending_drafts: TTLCache[str, PendingDraft] = TTLCache(maxsize=256, ttl=3600)
        self._pending_resubmit: TTLCache[str, str] = TTLCache(maxsize=256, ttl=86400)
        self._partial_drafts: TTLCache[str, tuple[str, ParsedRequest]] = TTLCache(
            maxsize=256, ttl=300
        )
        self._lock = threading.Lock()

    def set_draft(self, handle: str, draft: PendingDraft) -> bool:
        """Store draft for handle. Returns True if a previous draft was replaced."""
        with self._lock:
            had = handle in self._pending_drafts
            self._pending_drafts[handle] = draft
            return had

    def pop_draft(self, handle: str) -> PendingDraft | None:
        with self._lock:
            return self._pending_drafts.pop(handle, None)

    def set_resubmit(self, handle: str, request_id: str) -> None:
        with self._lock:
            self._pending_resubmit[handle] = request_id

    def pop_resubmit(self, handle: str) -> str | None:
        with self._lock:
            return self._pending_resubmit.pop(handle, None)

    def clear_resubmit(self, handle: str) -> None:
        with self._lock:
            self._pending_resubmit.pop(handle, None)

    def set_partial(self, handle: str, text: str, parsed: ParsedRequest) -> None:
        with self._lock:
            self._partial_drafts[handle] = (text, parsed)

    def clear_partial(self, handle: str) -> None:
        with self._lock:
            self._partial_drafts.pop(handle, None)

    def combine_partial_if_short(self, handle: str, text: str) -> str:
        """Combine text with existing partial draft if text is short; discard partial otherwise."""
        with self._lock:
            if handle in self._partial_drafts and len(text) <= 80:
                original, _ = self._partial_drafts.pop(handle)
                return f"{original} {text}"
            self._partial_drafts.pop(handle, None)
        return text

    def reset_for_new_request(self, handle: str) -> None:
        """Clear resubmit and partial state when user starts a fresh request."""
        with self._lock:
            self._pending_resubmit.pop(handle, None)
            self._partial_drafts.pop(handle, None)

    def discard_all(self, handle: str) -> bool:
        """Discard all draft state for handle. Returns True if a pending draft existed."""
        with self._lock:
            draft = self._pending_drafts.pop(handle, None)
            self._pending_resubmit.pop(handle, None)
            self._partial_drafts.pop(handle, None)
            return draft is not None
