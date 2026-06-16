from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from cachetools import TTLCache

if TYPE_CHECKING:
    from collections.abc import Callable

    from agent.domain.models import ActorContext, MessageSource
    from agent.parsing.request_parser import ParsedRequest
    from agent.persistence.base import WorkflowStore

LOGGER = logging.getLogger(__name__)

_DRAFT_TTL = 3600       # seconds — pending draft (1 hour)
_RESUBMIT_TTL = 86400   # seconds — pending resubmit (24 hours)
_PARTIAL_TTL = 300       # seconds — partial draft (5 minutes)


def _expiry_iso(ttl_seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=ttl_seconds)).isoformat()


class PendingDraft:
    __slots__ = ("business_reason", "parsed_request", "request_text", "requester", "source")

    def __init__(
        self,
        request_text: str,
        requester: ActorContext,
        parsed_request: ParsedRequest,
        business_reason: str | None,
        source: MessageSource,
    ) -> None:
        self.request_text = request_text
        self.requester = requester
        self.parsed_request = parsed_request
        self.business_reason = business_reason
        self.source = source


class DraftManager:
    """Thread-safe store for per-user draft, resubmit, and partial-draft state.

    Write-through cache: TTLCache for fast reads + TTL enforcement; optional
    workflow_store for persistent backing (survives container restarts).
    """

    def __init__(self, workflow_store: WorkflowStore | None = None) -> None:
        self._store = workflow_store
        # All three caches share _lock because TTLCache is not thread-safe.
        self._lock = threading.Lock()
        self._pending_drafts: TTLCache[str, PendingDraft] = TTLCache(
            maxsize=256, ttl=_DRAFT_TTL
        )
        self._pending_resubmit: TTLCache[str, str] = TTLCache(
            maxsize=256, ttl=_RESUBMIT_TTL
        )
        # _partial_drafts: too transient (5 min) to warrant persistent backing.
        self._partial_drafts: TTLCache[str, tuple[str, ParsedRequest]] = TTLCache(
            maxsize=256, ttl=_PARTIAL_TTL
        )

        if self._store is not None:
            self._load_from_store()

    # ── public API ───────────────────────────────────────────────────────────

    def set_draft(self, handle: str, draft: PendingDraft) -> bool:
        """Store draft for handle. Returns True if a previous draft was replaced."""
        with self._lock:
            had = handle in self._pending_drafts
            self._pending_drafts[handle] = draft
        self._run_async(self._persist_draft, handle, draft)
        return had

    def pop_draft(self, handle: str) -> PendingDraft | None:
        with self._lock:
            result = self._pending_drafts.pop(handle, None)
        if result is not None:
            self._run_async(self._delete_draft, handle)
        return result

    def set_resubmit(self, handle: str, request_id: str) -> None:
        with self._lock:
            self._pending_resubmit[handle] = request_id
        self._run_async(self._persist_resubmit, handle, request_id)

    def pop_resubmit(self, handle: str) -> str | None:
        with self._lock:
            result = self._pending_resubmit.pop(handle, None)
        if result is not None:
            self._run_async(self._delete_resubmit, handle)
        return result

    def clear_resubmit(self, handle: str) -> None:
        with self._lock:
            self._pending_resubmit.pop(handle, None)
        self._run_async(self._delete_resubmit, handle)

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
        self._run_async(self._delete_resubmit, handle)

    def discard_all(self, handle: str) -> bool:
        """Discard all draft state for handle. Returns True if a pending draft existed."""
        with self._lock:
            draft = self._pending_drafts.pop(handle, None)
            self._pending_resubmit.pop(handle, None)
            self._partial_drafts.pop(handle, None)
        if draft is not None:
            self._run_async(self._delete_draft, handle)
        self._run_async(self._delete_resubmit, handle)
        return draft is not None

    # ── startup load ─────────────────────────────────────────────────────────

    def _load_from_store(self) -> None:
        self._load_pending_drafts()
        self._load_pending_resubmits()

    def _load_pending_drafts(self) -> None:
        try:
            rows = self._store.load_pending_drafts()
            loaded = 0
            for row in rows:
                handle = row.get("handle", "")
                draft = _deserialize_draft(row)
                if handle and draft:
                    with self._lock:
                        self._pending_drafts[handle] = draft
                    loaded += 1
            if loaded:
                LOGGER.info("DraftManager: loaded %d pending drafts from store", loaded)
        except Exception as exc:
            LOGGER.warning("DraftManager: failed to load pending_drafts error=%s", exc)

    def _load_pending_resubmits(self) -> None:
        try:
            rows = self._store.load_pending_resubmit()
            loaded = 0
            for row in rows:
                handle = row.get("handle", "")
                request_id = row.get("request_id", "")
                if handle and request_id:
                    with self._lock:
                        self._pending_resubmit[handle] = request_id
                    loaded += 1
            if loaded:
                LOGGER.info("DraftManager: loaded %d pending resubmit entries from store", loaded)
        except Exception as exc:
            LOGGER.warning("DraftManager: failed to load pending_resubmit error=%s", exc)

    # ── async dispatch helper ────────────────────────────────────────────────

    def _run_async(self, fn: Callable[..., None], *args: object) -> None:
        if self._store is None:
            return
        threading.Thread(target=fn, args=args, daemon=True).start()

    # ── sync write helpers ───────────────────────────────────────────────────

    def _persist_draft(self, handle: str, draft: PendingDraft) -> None:
        try:
            data = {
                "request_text": draft.request_text,
                "requester_json": json.dumps(draft.requester.model_dump()),
                "parsed_json": json.dumps(asdict(draft.parsed_request)),
                "business_reason": draft.business_reason or "",
                "source_json": json.dumps(draft.source.model_dump()),
                "expires_at": _expiry_iso(_DRAFT_TTL),
            }
            self._store.upsert_pending_draft(handle, data)
        except Exception as exc:
            LOGGER.debug("DraftManager: persist_draft failed handle=%s error=%s", handle, exc)

    def _delete_draft(self, handle: str) -> None:
        try:
            self._store.delete_pending_draft(handle)
        except Exception as exc:
            LOGGER.debug("DraftManager: delete_draft failed handle=%s error=%s", handle, exc)

    def _persist_resubmit(self, handle: str, request_id: str) -> None:
        try:
            self._store.upsert_pending_resubmit(handle, request_id, _expiry_iso(_RESUBMIT_TTL))
        except Exception as exc:
            LOGGER.debug(
                "DraftManager: persist_resubmit failed handle=%s error=%s", handle, exc
            )

    def _delete_resubmit(self, handle: str) -> None:
        try:
            self._store.delete_pending_resubmit(handle)
        except Exception as exc:
            LOGGER.debug(
                "DraftManager: delete_resubmit failed handle=%s error=%s", handle, exc
            )


def _deserialize_draft(row: dict[str, str]) -> PendingDraft | None:
    try:
        from agent.domain.models import ActorContext, MessageSource
        from agent.parsing.request_parser import ParsedRequest

        parsed = ParsedRequest(**json.loads(row["parsed_json"]))
        requester = ActorContext(**json.loads(row["requester_json"]))
        source = MessageSource(**json.loads(row["source_json"]))
        return PendingDraft(
            request_text=row["request_text"],
            requester=requester,
            parsed_request=parsed,
            business_reason=row.get("business_reason") or None,
            source=source,
        )
    except Exception:
        return None
