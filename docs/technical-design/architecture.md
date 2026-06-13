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
    ->
RequestService <-> AuditService
    ->
WorkflowStore
    ->
GoogleSheetsWorkflowStore
    ->
Google Sheets
```

## Implementation Stack

Use one small, consistent stack for the first release.

### Language

- Python `3.11`

Why:

- fast to iterate
- good Telegram and Google API libraries
- good fit for a small AgentBase service

### Runtime

- `greennode-agentbase`

Why:

- already provides the runtime entrypoint and health interface needed for deployment
- avoids adding another web framework unless real internal APIs are needed later

### Core Libraries

- `pydantic`
- `PyYAML`
- `python-telegram-bot`
- `gspread`
- `google-auth`

Why:

- low boilerplate for configuration
- mature Telegram and Google Sheets integrations
- enough for the first useful workflow without extra framework weight

## Core Components

### Configuration Layer

- load `runtime.yaml`
- fall back to `runtime.example.yaml` when a local runtime file does not exist yet
- apply optional environment overrides when the deploy environment needs them
- expose typed config to the runtime
- keep `.env` outside the main config path

### TelegramAdapter

- receive Telegram text and commands
- normalize actor, chat, and message metadata
- send replies
- later send approver notifications

### AgentOrchestrator

- parse requester messages
- manage pending confirmation draft
- route approver actions
- return normalized response payloads

### RequestService

- create request
- resubmit after needs-info
- approve, reject, cancel
- enforce lifecycle rules through a finite state machine

### AuditService

- append immutable audit events
- return timeline by request ID

### WorkflowStore

The persistence interface.

Required operations:

- `initialize`
- `create_request`
- `update_request`
- `get_request`
- `create_request_conversation`
- `create_audit_event`
- `list_audit_events`

### GoogleSheetsWorkflowStore

The first concrete persistence adapter.

Responsibilities:

- authenticate with Google service account
- open the configured spreadsheet
- auto-create worksheets
- map domain records to rows
- keep Google Sheets detail out of workflow services

## Persistence Decision

### Chosen Now

- `Google Sheets`

### Why

- no separate database deployment
- easy shared access for a small internal team
- enough for low-volume request and audit data

### Tradeoffs

- limited write throughput
- weak fit for multi-replica concurrent writes
- limited reporting compared with a SQL database

Because of those tradeoffs, persistence is wrapped behind `WorkflowStore` from the start.

## Configuration Pattern

Use:

- YAML for structured defaults
- runtime environment variables only when deployment needs overrides

Files:

- `runtime.yaml`
- `runtime.example.yaml`
- `.agentbase/deploy.env` for deploy-time overrides only

Later only:

- `ai-review.yaml`

## Workflow State Control

Use an explicit finite state machine in `RequestService`.

Rules:

- adapters must not mutate `review_status` directly
- every transition goes through a service method
- invalid transitions fail safely
- terminal decisions are auditable
- state-changing actions should prefer explicit request ID

## Minimum Persistent Records

Keep three logical record sets:

- `requests`
- `audit_events`
- `request_conversations`

That is enough for the first release.

## Minimal Technical Shape

Keep the runtime intentionally small:

- one Python service
- one Telegram adapter
- one `WorkflowStore` interface
- one `GoogleSheetsWorkflowStore` implementation
- one explicit state machine in `RequestService`
- no separate web frontend
- no separate worker
- no separate AI service

## Deliberately Not Chosen Now

### SQL Database First

Not chosen for the first release because:

- adds deployment and operations overhead
- the current product goal is still to prove the workflow itself

### FastAPI Or Another Extra Web Layer

Not chosen now because:

- AgentBase runtime already covers the immediate server need
- there is no required user-facing web surface yet

### LangChain Or LangGraph

Not chosen now because:

- the first workflow does not need agentic planning
- it would add architecture before proving the product feature

## Upgrade Path

If the workflow is proven useful later:

1. move persistence from Google Sheets to a SQL database if write volume or reporting needs grow
2. add a read-only inspection UI
3. add group-chat support
4. add AI diff analysis

## AI Placement Later

AI review assistance is not part of the first release.

When added later:

- the orchestrator decides when to request AI analysis
- an `AIReviewService` calls the model provider
- AI output is advisory only
- workflow state still stays in `RequestService`
- keep the detailed future design in [AI Review Assistance](../future/ai-review-assistance.md)

For locked release decisions, see [Scope And Channel Decision](./scope-and-channel-decision.md).
