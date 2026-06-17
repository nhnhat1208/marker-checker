# Workflow Lifecycle

## States

The system currently uses these workflow-visible states:

1. `draft`
2. `submitted`
3. `in_review`
4. `needs_info`
5. `approved`
6. `rejected`
7. `cancelled`

In practice, users most often see `submitted`, `needs_info`, `approved`, `rejected`, and `cancelled`. `draft` and `in_review` are still part of the internal lifecycle and should be documented consistently.

## Transition Rules

- a real request is created only after requester confirmation
- approver actions are explicit and target exactly one request
- `submitted` and `in_review` can move to `approved`, `rejected`, `needs_info`, or `cancelled` where allowed
- requester can resubmit after `needs_info`
- requester can discard a pending draft before submission
- `approved`, `rejected`, and `cancelled` are terminal
- every meaningful transition creates an audit event

## Lifecycle

### 1. Drafting

1. requester sends a message in natural language or structured web input
2. the agent extracts or asks for:
   - `target_label`
   - `change_from_summary`
   - `change_to_summary`
   - `approver_handle`
3. if required fields are missing, the agent asks only for the missing pieces
4. the agent shows a normalized draft
5. requester confirms or discards the draft

### 2. Submission

1. requester confirms the pending draft
2. the request is persisted with a request ID
3. the request enters active review state
4. the approver is notified on the relevant channel when possible

### 3. Approver Review

1. approver receives the request summary
2. approver can:
   - approve
   - reject
   - request more info
   - cancel where allowed
3. the agent records the decision, updates status, and writes the audit trail

### 4. Needs-Info Loop

1. approver moves the request to `needs_info`
2. requester sends updated details
3. the agent parses the update and resubmits the request
4. the audit trail keeps the revision history

### 5. Lookup Flows

The agent supports read-oriented request operations in addition to status lookup:

- `status` / `lookup` for a specific request ID
- `history` for the audit timeline of a request
- `search` by target name
- `my requests` / `my pending` for the requester’s active items
- `my approvals` / `pending approvals` for items waiting on the current approver

## Commands And Queries

Common explicit commands:

- `/confirm` — submit the current pending draft
- `/discard` — drop the current pending draft without submitting
- `/approve REQ-... [note]` — approve a request
- `/reject REQ-... [reason]` — reject a request
- `/needinfo REQ-... [question]` — request more details from the requester
- `/cancel REQ-... [note]` — cancel an active request when allowed
- `/status REQ-...` — inspect the current request summary
- `/history REQ-...` — inspect the audit timeline

Common freeform query intents:

- `my requests`
- `pending approvals`
- `search api-gateway`
- `show request REQ-1234`
- `history REQ-1234`

## Interaction Model

- natural-language chat is the primary UX
- slash commands are shortcuts, not the only path
- explicit request ID is preferred for state-changing actions
- management intents can also be recognized from free text
- the agent must not guess when request context is ambiguous

## Audit Events

Current audit event types include:

- `request_submitted`
- `missing_fields_requested`
- `request_draft_updated`
- `approver_notified`
- `needs_info_requested`
- `request_resubmitted`
- `decision_recorded`
- `request_cancelled`
- `lookup_performed`
