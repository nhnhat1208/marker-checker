from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.config import MemoryConfig

LOGGER = logging.getLogger(__name__)

_SESSION_SUBMISSIONS = "submissions"
_SESSION_DECISIONS = "decisions"
_SESSION_CONVERSATION = "conversation"


class AgentMemoryService:
    """Wraps AgentBase Memory Service for user preference and approver behavior learning.

    All write operations are fire-and-forget (background thread) — they never block
    the request flow. Read operations are synchronous but fail-safe: any exception
    returns None so the caller can continue without memory context.
    """

    def __init__(self, config: MemoryConfig) -> None:
        self._config = config
        self._client = None
        if config.enabled and config.memory_id:
            try:
                from greennode_agentbase.memory import MemoryClient
                self._client = MemoryClient()
                LOGGER.info("AgentMemoryService initialized memory_id=%s", config.memory_id)
            except Exception as exc:
                LOGGER.warning("AgentMemoryService: failed to init MemoryClient error=%s", exc)

    @property
    def enabled(self) -> bool:
        return self._client is not None and bool(self._config.memory_id)

    # --- writes (fire-and-forget) ---

    def log_submission(self, requester_handle: str, target: str, approver: str) -> None:
        message = (
            f"User {requester_handle} submitted a change request: "
            f"target={target}, assigned approver={approver}"
        )
        self._log_event_async(
            actor_id=_sanitize_handle(requester_handle),
            session_id=_SESSION_SUBMISSIONS,
            role="user",
            message=message,
        )

    def log_approver_decision(
        self,
        approver_handle: str,
        target: str,
        action: str,
        change_from: str,
        change_to: str,
    ) -> None:
        message = (
            f"Approver {approver_handle} {action}d a change request: "
            f"target={target}, change: {change_from} → {change_to}"
        )
        self._log_event_async(
            actor_id=_sanitize_handle(approver_handle),
            session_id=_SESSION_DECISIONS,
            role="assistant",
            message=message,
        )

    def log_user_message(self, user_handle: str, message: str) -> None:
        self._log_event_async(
            actor_id=_sanitize_handle(user_handle),
            session_id=_SESSION_CONVERSATION,
            role="user",
            message=message[:500],
        )

    # --- reads (sync, fail-safe) ---

    def get_user_preferences(self, user_handle: str) -> str | None:
        """Return a short context string about this user's preferences, or None."""
        if not self.enabled or not self._config.user_pref_strategy_id:
            return None
        try:
            namespace = (
                f"/strategies/{self._config.user_pref_strategy_id}"
                f"/actors/{_sanitize_handle(user_handle)}"
            )
            records = self._client.search_memory_records(  # type: ignore[union-attr]
                id=self._config.memory_id,
                namespace=namespace,
                body={"query": f"preferences and habits of {user_handle}", "limit": 5},
            )
            return _format_records(records)
        except Exception as exc:
            LOGGER.debug("get_user_preferences failed user=%s error=%s", user_handle, exc)
            return None

    def get_approver_patterns(self, approver_handle: str) -> str | None:
        """Return a short context string about this approver's decision patterns, or None."""
        if not self.enabled or not self._config.approver_behavior_strategy_id:
            return None
        try:
            namespace = (
                f"/strategies/{self._config.approver_behavior_strategy_id}"
                f"/actors/{_sanitize_handle(approver_handle)}"
            )
            records = self._client.search_memory_records(  # type: ignore[union-attr]
                id=self._config.memory_id,
                namespace=namespace,
                body={"query": f"approval patterns and behavior of {approver_handle}", "limit": 5},
            )
            return _format_records(records)
        except Exception as exc:
            LOGGER.debug("get_approver_patterns failed approver=%s error=%s", approver_handle, exc)
            return None

    def get_recent_messages(self, user_handle: str, limit: int = 5) -> list[str]:
        """Return recent conversation messages for this user (newest first)."""
        if not self.enabled:
            return []
        try:
            result = self._client.list_events(  # type: ignore[union-attr]
                id=self._config.memory_id,
                actorId=_sanitize_handle(user_handle),
                sessionId=_SESSION_CONVERSATION,
                size=limit,
            )
            events = getattr(result, "list_data", None) or (result if isinstance(result, list) else [])
            messages = []
            for event in events:
                payload = getattr(event, "payload", None) or {}
                msg = getattr(payload, "message", None) or (
                    payload.get("message") if isinstance(payload, dict) else None
                )
                if msg:
                    messages.append(msg)
            return messages
        except Exception as exc:
            LOGGER.debug("get_recent_messages failed user=%s error=%s", user_handle, exc)
            return []

    # --- private ---

    def _log_event_async(
        self, *, actor_id: str, session_id: str, role: str, message: str
    ) -> None:
        if not self.enabled:
            return
        thread = threading.Thread(
            target=self._log_event,
            kwargs={"actor_id": actor_id, "session_id": session_id, "role": role, "message": message},
            daemon=True,
        )
        thread.start()

    def _log_event(self, *, actor_id: str, session_id: str, role: str, message: str) -> None:
        try:
            self._client.create_event(  # type: ignore[union-attr]
                id=self._config.memory_id,
                actorId=actor_id,
                sessionId=session_id,
                body={
                    "payload": {
                        "type": "conversational",
                        "role": role,
                        "message": message,
                    }
                },
            )
        except Exception as exc:
            LOGGER.debug("Memory log_event failed actor=%s error=%s", actor_id, exc)


def _sanitize_handle(handle: str) -> str:
    return handle.lstrip("@").strip() or "unknown"


def _format_records(records: object) -> str | None:
    items = records if isinstance(records, list) else getattr(records, "list_data", None) or []

    texts = []
    for r in items:
        memory_text = getattr(r, "memory", None) or (r.get("memory") if isinstance(r, dict) else None)
        if memory_text:
            texts.append(str(memory_text).strip())

    return "\n".join(texts) if texts else None
