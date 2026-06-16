from __future__ import annotations

import json
import logging
import re
import threading
from contextlib import contextmanager
from typing import TYPE_CHECKING
from uuid import uuid4

import psycopg2
import psycopg2.extras
from psycopg2.pool import ThreadedConnectionPool

from agent.domain.models import (
    AuditEventRecord,
    RequestConversationRecord,
    RequestRecord,
)

if TYPE_CHECKING:
    from collections.abc import Generator

    from psycopg2.extensions import connection

LOGGER = logging.getLogger(__name__)

_DDL = """
CREATE TABLE IF NOT EXISTS requests (
    request_id             TEXT PRIMARY KEY,
    request_text           TEXT NOT NULL DEFAULT '',
    structured_payload_json TEXT,
    requester_name         TEXT,
    requester_handle       TEXT NOT NULL DEFAULT '',
    approver_name          TEXT,
    approver_handle        TEXT NOT NULL DEFAULT '',
    target_label           TEXT NOT NULL DEFAULT '',
    target_object_type     TEXT,
    change_from_summary    TEXT NOT NULL DEFAULT '',
    change_to_summary      TEXT NOT NULL DEFAULT '',
    business_reason        TEXT,
    review_status          TEXT NOT NULL DEFAULT 'draft',
    current_revision       INTEGER NOT NULL DEFAULT 1,
    last_submitted_revision INTEGER NOT NULL DEFAULT 1,
    last_submitted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at            TIMESTAMPTZ,
    resolution_note        TEXT,
    resolved_by_name       TEXT,
    resolved_by_handle     TEXT,
    cancelled_at           TIMESTAMPTZ,
    cancelled_by_handle    TEXT,
    cancellation_note      TEXT,
    origin_channel_id      TEXT,
    origin_thread_id       TEXT,
    origin_message_id      TEXT
);

CREATE TABLE IF NOT EXISTS audit_events (
    event_id         TEXT PRIMARY KEY,
    event_sequence   INTEGER NOT NULL DEFAULT 0,
    request_id       TEXT NOT NULL,
    event_type       TEXT NOT NULL,
    actor_name       TEXT,
    actor_handle     TEXT NOT NULL DEFAULT '',
    actor_kind       TEXT NOT NULL DEFAULT 'user',
    request_revision INTEGER,
    occurred_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    summary          TEXT NOT NULL DEFAULT '',
    event_payload    JSONB NOT NULL DEFAULT '{}',
    source_channel   TEXT NOT NULL DEFAULT 'telegram',
    thread_id        TEXT,
    source_message_id TEXT
);

CREATE TABLE IF NOT EXISTS request_conversations (
    row_id            TEXT PRIMARY KEY,
    request_id        TEXT NOT NULL,
    actor_handle      TEXT NOT NULL DEFAULT '',
    conversation_role TEXT NOT NULL DEFAULT '',
    channel_id        TEXT,
    thread_id         TEXT,
    conversation_id   TEXT,
    linked_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_registry (
    handle     TEXT PRIMARY KEY,
    chat_id    TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS pending_drafts (
    handle         TEXT PRIMARY KEY,
    request_text   TEXT NOT NULL DEFAULT '',
    requester_json TEXT NOT NULL DEFAULT '{}',
    parsed_json    TEXT NOT NULL DEFAULT '{}',
    business_reason TEXT,
    source_json    TEXT NOT NULL DEFAULT '{}',
    expires_at     TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS pending_resubmit (
    handle     TEXT PRIMARY KEY,
    request_id TEXT NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS user_profiles (
    email        TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    avatar_url   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_events_request_id
    ON audit_events(request_id);
CREATE INDEX IF NOT EXISTS idx_conversations_request_id
    ON request_conversations(request_id);
"""

_MIGRATIONS = (
    "ALTER TABLE requests ADD COLUMN IF NOT EXISTS structured_payload_json TEXT",
)


def _mask_dsn(dsn: str) -> str:
    return re.sub(r":([^:@/]+)@", ":***@", dsn)


class PostgresWorkflowStore:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._pool: ThreadedConnectionPool | None = None
        self._init_lock = threading.Lock()

    # ── lifecycle ────────────────────────────────────────────────────────────

    def initialize(self) -> None:
        with self._init_lock:
            self._pool = ThreadedConnectionPool(minconn=1, maxconn=5, dsn=self._dsn)
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(_DDL)
            for statement in _MIGRATIONS:
                cur.execute(statement)
        LOGGER.info("PostgresWorkflowStore initialized dsn=%s", _mask_dsn(self._dsn))

    @contextmanager
    def _conn(self) -> Generator[connection, None, None]:
        assert self._pool is not None, "initialize() must be called first"
        conn = self._pool.getconn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            self._pool.putconn(conn)

    # ── requests ─────────────────────────────────────────────────────────────

    def create_request(self, request: RequestRecord) -> RequestRecord:
        sql = """
        INSERT INTO requests (
            request_id, request_text, structured_payload_json, requester_name, requester_handle,
            approver_name, approver_handle, target_label, target_object_type,
            change_from_summary, change_to_summary, business_reason, review_status,
            current_revision, last_submitted_revision, last_submitted_at,
            created_at, updated_at, resolved_at, resolution_note,
            resolved_by_name, resolved_by_handle, cancelled_at,
            cancelled_by_handle, cancellation_note, origin_channel_id,
            origin_thread_id, origin_message_id
        ) VALUES (
            %(request_id)s, %(request_text)s, %(structured_payload_json)s,
            %(requester_name)s, %(requester_handle)s, %(approver_name)s,
            %(approver_handle)s, %(target_label)s, %(target_object_type)s,
            %(change_from_summary)s, %(change_to_summary)s, %(business_reason)s,
            %(review_status)s, %(current_revision)s, %(last_submitted_revision)s,
            %(last_submitted_at)s, %(created_at)s, %(updated_at)s, %(resolved_at)s,
            %(resolution_note)s, %(resolved_by_name)s, %(resolved_by_handle)s,
            %(cancelled_at)s, %(cancelled_by_handle)s, %(cancellation_note)s,
            %(origin_channel_id)s, %(origin_thread_id)s, %(origin_message_id)s
        )
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, request.model_dump())
        return request

    def update_request(self, request: RequestRecord) -> RequestRecord:
        sql = """
        UPDATE requests SET
            request_text = %(request_text)s,
            structured_payload_json = %(structured_payload_json)s,
            requester_name = %(requester_name)s,
            requester_handle = %(requester_handle)s,
            approver_name = %(approver_name)s,
            approver_handle = %(approver_handle)s,
            target_label = %(target_label)s,
            target_object_type = %(target_object_type)s,
            change_from_summary = %(change_from_summary)s,
            change_to_summary = %(change_to_summary)s,
            business_reason = %(business_reason)s,
            review_status = %(review_status)s,
            current_revision = %(current_revision)s,
            last_submitted_revision = %(last_submitted_revision)s,
            last_submitted_at = %(last_submitted_at)s,
            updated_at = %(updated_at)s,
            resolved_at = %(resolved_at)s,
            resolution_note = %(resolution_note)s,
            resolved_by_name = %(resolved_by_name)s,
            resolved_by_handle = %(resolved_by_handle)s,
            cancelled_at = %(cancelled_at)s,
            cancelled_by_handle = %(cancelled_by_handle)s,
            cancellation_note = %(cancellation_note)s,
            origin_channel_id = %(origin_channel_id)s,
            origin_thread_id = %(origin_thread_id)s,
            origin_message_id = %(origin_message_id)s
        WHERE request_id = %(request_id)s
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, request.model_dump())
        return request

    def get_request(self, request_id: str) -> RequestRecord | None:
        with self._conn() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(
                "SELECT * FROM requests WHERE request_id = %s", (request_id,)
            )
            row = cur.fetchone()
        if row is None:
            return None
        return RequestRecord(**dict(row))

    def list_requests(self) -> list[RequestRecord]:
        with self._conn() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute("SELECT * FROM requests ORDER BY created_at")
            rows = cur.fetchall()
        return [RequestRecord(**dict(row)) for row in rows]

    # ── conversations ─────────────────────────────────────────────────────────

    def create_request_conversation(
        self, conversation: RequestConversationRecord
    ) -> RequestConversationRecord:
        if not conversation.row_id:
            conversation = conversation.model_copy(update={"row_id": str(uuid4())})
        sql = """
        INSERT INTO request_conversations
            (row_id, request_id, actor_handle, conversation_role,
             channel_id, thread_id, conversation_id, linked_at, last_seen_at)
        VALUES
            (%(row_id)s, %(request_id)s, %(actor_handle)s, %(conversation_role)s,
             %(channel_id)s, %(thread_id)s, %(conversation_id)s, %(linked_at)s, %(last_seen_at)s)
        ON CONFLICT (row_id) DO NOTHING
        """
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(sql, conversation.model_dump())
        return conversation

    # ── audit events ─────────────────────────────────────────────────────────

    def create_audit_event(self, event: AuditEventRecord) -> AuditEventRecord:
        event_id = event.event_id or str(uuid4())
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "SELECT COALESCE(MAX(event_sequence), 0) + 1 FROM audit_events "
                "WHERE request_id = %s",
                (event.request_id,),
            )
            sequence = cur.fetchone()[0]
            cur.execute(
                """
                INSERT INTO audit_events (
                    event_id, event_sequence, request_id, event_type,
                    actor_name, actor_handle, actor_kind, request_revision,
                    occurred_at, summary, event_payload, source_channel,
                    thread_id, source_message_id
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    event_id, sequence, event.request_id, event.event_type,
                    event.actor_name, event.actor_handle, event.actor_kind,
                    event.request_revision, event.occurred_at, event.summary,
                    json.dumps(event.event_payload), event.source_channel,
                    event.thread_id, event.source_message_id,
                ),
            )
        return event.model_copy(update={"event_id": event_id, "event_sequence": sequence})

    def list_audit_events(self, request_id: str) -> list[AuditEventRecord]:
        with self._conn() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(
                "SELECT * FROM audit_events WHERE request_id = %s "
                "ORDER BY event_sequence",
                (request_id,),
            )
            rows = cur.fetchall()
        return [AuditEventRecord(**dict(row)) for row in rows]

    # ── chat_registry ─────────────────────────────────────────────────────────

    def load_chat_registry(self) -> dict[str, str]:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT handle, chat_id FROM chat_registry")
            return {row[0]: row[1] for row in cur.fetchall()}

    def upsert_chat_id(self, handle: str, chat_id: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO chat_registry (handle, chat_id)
                VALUES (%s, %s)
                ON CONFLICT (handle) DO UPDATE SET chat_id = EXCLUDED.chat_id,
                    updated_at = NOW()
                """,
                (handle, chat_id),
            )

    # ── pending_drafts ────────────────────────────────────────────────────────

    def load_pending_drafts(self) -> list[dict[str, str]]:
        with self._conn() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute("SELECT * FROM pending_drafts WHERE expires_at > NOW()")
            return [dict(row) for row in cur.fetchall()]

    def upsert_pending_draft(self, handle: str, data: dict[str, str]) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pending_drafts
                    (handle, request_text, requester_json, parsed_json,
                     business_reason, source_json, expires_at)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                ON CONFLICT (handle) DO UPDATE SET
                    request_text    = EXCLUDED.request_text,
                    requester_json  = EXCLUDED.requester_json,
                    parsed_json     = EXCLUDED.parsed_json,
                    business_reason = EXCLUDED.business_reason,
                    source_json     = EXCLUDED.source_json,
                    expires_at      = EXCLUDED.expires_at
                """,
                (
                    handle,
                    data.get("request_text", ""),
                    data.get("requester_json", "{}"),
                    data.get("parsed_json", "{}"),
                    data.get("business_reason") or None,
                    data.get("source_json", "{}"),
                    data.get("expires_at"),
                ),
            )

    def delete_pending_draft(self, handle: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute("DELETE FROM pending_drafts WHERE handle = %s", (handle,))

    # ── pending_resubmit ──────────────────────────────────────────────────────

    def load_pending_resubmit(self) -> list[dict[str, str]]:
        with self._conn() as conn, conn.cursor(
            cursor_factory=psycopg2.extras.RealDictCursor
        ) as cur:
            cur.execute(
                "SELECT handle, request_id FROM pending_resubmit "
                "WHERE expires_at > NOW()"
            )
            return [dict(row) for row in cur.fetchall()]

    def upsert_pending_resubmit(
        self, handle: str, request_id: str, expires_at: str
    ) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pending_resubmit (handle, request_id, expires_at)
                VALUES (%s, %s, %s)
                ON CONFLICT (handle) DO UPDATE SET
                    request_id = EXCLUDED.request_id,
                    expires_at = EXCLUDED.expires_at
                """,
                (handle, request_id, expires_at),
            )

    def delete_pending_resubmit(self, handle: str) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                "DELETE FROM pending_resubmit WHERE handle = %s", (handle,)
            )

    # ── user_profiles ─────────────────────────────────────────────────────────

    def upsert_user_profile(
        self, email: str, display_name: str, avatar_url: str
    ) -> None:
        with self._conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles (email, display_name, avatar_url)
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    avatar_url   = EXCLUDED.avatar_url
                """,
                (email, display_name, avatar_url),
            )
