# Technical Architecture

## Architecture Overview

Recommended logical components:

1. Chat Interface Layer
2. Agent Orchestrator
3. Request Service
4. Audit Service
5. Conversation Context Store
6. Notification Service
7. Optional AI Review Assistance Service

## Component Responsibilities

### Chat Interface Layer

Handles direct chat conversations for requester, approver, and lookup users.

### Agent Orchestrator

Manages workflow state, message parsing, prompt behavior, and tool calls.

### Request Service

Stores request records and enforces state transitions.

### Audit Service

Stores immutable event timeline and searchable evidence.

### Conversation Context Store

Maps one request ID to one or more actor-specific chat contexts so requester and approver chats resolve to the same workflow record.

### Notification Service

Sends review requests, reminders, and final outcomes.

### Optional AI Review Assistance Service

AI review assistance component for before/after analysis.

## Minimum Agent Tools

Recommended minimum tool/actions for the agent:

- `ingest_channel_event`
- `parse_request_message`
- `validate_required_fields`
- `resolve_approver_handle`
- `create_request`
- `update_request`
- `confirm_request_submission`
- `store_request_revision`
- `link_request_conversation`
- `resolve_request_context`
- `notify_approver`
- `request_more_info`
- `resubmit_request`
- `cancel_request`
- `record_approval`
- `record_rejection`
- `get_request`
- `lookup_request`
- `get_audit_timeline`
- `notify_actor`
- `analyze_diff` in later stages

Each tool should return structured data so the agent can produce consistent chat responses.

## Required Persistent Records

The initial release should treat these records as required, not optional:

- `requests`
- `audit_events`
- `request_conversations`

One of these revision storage approaches must also be chosen before implementation:

- store submitted revision snapshots inside `audit_events.event_payload`
- add a dedicated `request_revisions` store and reference it from audit events

Recommended default:

- keep revision snapshots in `audit_events` for the first release if query needs are simple
- add `request_revisions` immediately if approvers or auditors need clean revision-by-revision browsing

## Idempotency And Duplicate Delivery Handling

Chat integrations will eventually deliver duplicate events, retry callbacks, or repeated button presses. The architecture should handle this explicitly.

Required behavior:

- Every inbound message or action should have a stable deduplication key such as `source_channel + channel_id + source_message_id + actor_handle`.
- Reprocessing the same inbound event must not create a duplicate request.
- Reprocessing the same approve, reject, cancel, or needs-info action must not create duplicate terminal or transition events.
- If a repeated event is detected, the system should return the already-known request state or decision result as a safe no-op response.
- Terminal decisions should be guarded by current `review_status` and `last_submitted_revision`.

Recommended implementation options:

- lightweight inbox table for processed inbound events
- unique constraints on channel event keys where the adapter supports them
- idempotent state transition methods in the request service

## Non-Functional Requirements

- Audit records must be durable and queryable.
- Request IDs must be unique and human-readable.
- State transitions should be idempotent and auditable.
- The system should support asynchronous chat and delayed responses.
- The same request must be safely resolvable from multiple linked chat contexts.
- The system should be observable with logs, metrics, and traceable request execution.
- Latency should feel conversational for common chat actions.
- The system should degrade safely if AI summarization fails.

## Decisions Needed Before Implementation

These choices affect the architecture and should be confirmed explicitly:

If no explicit alternative is recorded, implementation should follow the recommended default.

| Decision | Options | Recommended Default |
|---|---|---|
| Primary chat channel | Telegram 1:1, Slack DM, internal chat adapter | Telegram 1:1 |
| Persistence mode | SQLite, PostgreSQL | PostgreSQL for shared internal deployment; SQLite only for a controlled single-instance environment |
| Revision storage | `audit_events` payload only, separate `request_revisions` store | `audit_events` payload only unless revision browsing is a first-class need |
| Telegram transport | Long polling, webhook | Long polling first |
