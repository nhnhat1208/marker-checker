# Technical Architecture

## Goal

Build one simple approval tool first:

- requester submits a change request
- approver resolves it
- lookup by request ID works
- audit history explains what happened

The design should stay small until that workflow is proven useful.

## Runtime Shape

```text
Telegram User
    ->
TelegramAdapter
    ->
AgentOrchestrator
    |-> FreeformIntentRouter   (regex, fast path)
    |-> RequestInputAssistant  (LLM: intent classify + request parse, optional)
    ->
RequestService <-> AuditService
    ->
WorkflowStore
    ->
GoogleSheetsWorkflowStore
    ->
Google Sheets
```

## Package Structure

```text
marker_checker_agent/
├── config.py          — typed config with pydantic-settings env override
├── orchestrator.py    — message routing and draft lifecycle
├── runtime.py         — AgentBase entrypoint wiring
├── time_utils.py
├── ai/
│   ├── types.py       — ClassifiedIntent, AssistedParseResult, MANAGEMENT_OPERATIONS
│   ├── prompts.py     — all LLM system prompts and user prompt builders
│   └── assistant.py   — RequestInputAssistant protocol + OpenAI-compatible impl
├── parsing/
│   ├── intent_router.py   — FreeformIntentRouter: regex-based operation routing
│   └── request_parser.py  — ParsedRequest, parse_request_text
├── domain/
│   ├── enums.py       — ReviewStatus, AuditEventType, Operation, ResponseStatus
│   └── models.py      — RequestRecord, AuditEventRecord, RequestConversationRecord
├── services/
│   ├── request_service.py — lifecycle FSM, create/approve/reject/cancel/resubmit
│   └── audit_service.py   — append-only audit events
├── persistence/
│   ├── base.py            — WorkflowStore interface
│   ├── google_sheets.py   — GoogleSheetsWorkflowStore
│   └── google_sheets_mapper.py
└── adapters/
    └── telegram_adapter.py
```

## Implementation Stack

### Language

- Python `3.11+`

### Dependency Management

- `uv` + `pyproject.toml`

### Runtime

- `greennode-agentbase`

### Core Libraries

| Library | Purpose |
| --- | --- |
| `pydantic` | Typed config models and domain validation |
| `pydantic-settings` | Automatic env var override for config classes |
| `PyYAML` | YAML config file loading |
| `python-telegram-bot` | Telegram polling and command handling |
| `gspread` + `google-auth` | Google Sheets persistence |
| `httpx` | HTTP client for LLM API calls |

## Core Components

### Configuration Layer

- load `runtime.yaml`, fall back to `runtime.example.yaml`
- each config class (`TelegramConfig`, `GoogleSheetsConfig`, `AIConfig`) extends `pydantic-settings` `BaseSettings` with an env prefix — env vars override YAML values automatically
- `_validate_runtime_config` enforces required fields at startup with clear error messages

### FreeformIntentRouter

- fast regex-based routing for management operations (lookup, history, cancel, needinfo, resubmit, my_pending, pending_approvals)
- supports both English and Vietnamese keywords
- returns `RoutedIntent(operation: Operation, request_id, note, text)`
- no external calls, always runs first

### RequestInputAssistant (LLM, optional)

Two capabilities, both gated by `ai.enabled`:

1. **`classify_intent`** — called when regex routing misses; asks the LLM to classify the operation (max 80 tokens). Routes management operations without requiring exact syntax.
2. **`assist_request_text`** — called when pattern parsing fails; asks the LLM to extract structured request fields. Returns `AssistedParseResult` with validation errors and guidance.

Uses OpenAI-compatible `/v1/chat/completions`. Any compatible provider works.

### AgentOrchestrator

Intent routing order:

1. `/confirm` shortcut
2. `FreeformIntentRouter` (regex)
3. `parse_request_text` (regex)
4. `classify_intent` (LLM, if enabled)
5. `assist_request_text` (LLM, if enabled)
6. `needs_input` fallback

### RequestService

- enforces FSM lifecycle transitions
- adapters must not mutate `review_status` directly
- every transition goes through a service method; invalid transitions raise `InvalidTransitionError`

### AuditService

- append-only audit events via `AuditEventType` enum
- `list_timeline` returns events in sequence order

### WorkflowStore

The persistence interface. Required operations: `initialize`, `create_request`, `update_request`, `get_request`, `create_audit_event`, `list_audit_events`.

### GoogleSheetsWorkflowStore

- authenticates with Google service account (file or base64 JSON)
- auto-creates worksheets on `initialize`
- maps domain records to rows via `google_sheets_mapper`
- keeps Google Sheets detail outside workflow services

## Domain Enums

| Enum | Values |
| --- | --- |
| `ReviewStatus` | `draft submitted in_review needs_info approved rejected cancelled` |
| `AuditEventType` | `request_submitted approver_notified decision_recorded ...` |
| `Operation` | `approve reject needinfo cancel lookup history resubmit my_pending pending_approvals confirm new_request unknown` |
| `ResponseStatus` | `ok error submitted missing_fields confirmation_required needs_input` |

All are `StrEnum` — values are plain strings, compatible with JSON serialization and string comparisons.

## Persistence Decision

### Chosen

- Google Sheets

### Why

- no separate database deployment
- easy shared access for a small internal team

### Tradeoffs

- limited write throughput — keep one replica to avoid write contention
- weak fit for multi-replica concurrent writes
- limited reporting vs. SQL

Persistence is behind `WorkflowStore` so it can be swapped later.

## Configuration Pattern

- YAML for structured defaults (`runtime.yaml`)
- env vars only for deploy-time overrides (`.agentbase/deploy.env`)
- `pydantic-settings` reads env vars automatically with typed coercion — no manual override code

## Upgrade Path

If the workflow is proven useful:

1. swap Google Sheets for a SQL backend via `WorkflowStore`
2. add read-only inspection UI
3. add group-chat support
4. expand AI to diff analysis (see [AI Review Assistance](../future/ai-review-assistance.md))
