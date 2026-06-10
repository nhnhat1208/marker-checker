# Implementation Plan

## Delivery Mindset

This plan targets a simple but correct first release.

The goal is not to build a throwaway bot. The goal is to build a useful tool with a narrow scope, clean workflow rules, and a foundation that can be extended later.

Planning assumptions:

- One primary engineer with AI coding assistance
- One primary delivery channel for the initial release
- One lightweight change schema with optional metadata
- No heavy custom frontend in the first release
- No RBAC or permission-directory integration in the initial release

## Decisions Needed Before Build Starts

These choices have multiple valid options. They should be written down explicitly so implementation does not drift.

If no alternative is explicitly approved, implementation should use the recommended default in this table.

| Decision | Options | Recommended Default | Why |
|---|---|---|---|
| Primary channel | Telegram 1:1, Slack DM, internal chat | Telegram 1:1 | Best fit for explicit approval chat flow |
| Persistence backend | PostgreSQL, SQLite | PostgreSQL for shared deployment; SQLite only for controlled single-instance use | Better durability for an audit-oriented tool |
| Revision storage | `audit_events` snapshots, separate `request_revisions` store | `audit_events` snapshots first | Simpler initial implementation with preserved evidence |
| Telegram transport | Long polling, webhook | Long polling | Lower setup complexity |

## Initial Release Goal

Deliver one working end-to-end approval workflow where:

- requester can send a simple change request
- tagged approver can review and resolve it
- lookup user can retrieve request status and basic history
- the system stores a durable audit trail for every important action

## Scope Boundary

### Must Build

- simple request intake from one message
- mandatory field validation before submission
- resolvable approver validation
- inbound event deduplication
- tagged approver notification
- approve, reject, and needs-info actions
- request persistence
- request-to-conversation mapping
- audit event persistence
- request lookup by request ID
- one chat-channel integration

### Should Build If Time Allows

- participant-safe search by target label or handle
- conversation summary command
- read-only request history view

### Defer From Initial Release

- full web application
- rich group-chat workflow
- AI diff analysis
- attachments and file upload handling
- RBAC and permission access
- reminder and escalation automation
- downstream execution workflow
- multiple object-specific forms

## Delivery Phases

### Phase: Initial Release

This phase should produce the first useful version of the tool.

#### Milestone: Workflow Core

Target outcome:

- stable lightweight request data model
- `review_status` transitions working
- audit events recorded for each state change

Functionality:

- parse simple request message
- show normalized request summary
- require requester confirmation before submission
- validate required submit fields
- deduplicate inbound channel events
- create request
- update request when more info is supplied
- resolve request context safely
- store approver handle
- reject free-text-only approver identities at submit time
- store request revision
- link requester and approver conversation contexts
- record approval action
- record rejection action
- cancel request
- store audit events

#### Milestone: Single-Channel Experience

Target outcome:

- requester and approver can use one real channel end to end

Functionality:

- requester starts request from channel
- approver receives request notification
- approver can approve, reject, or request more info
- requester can respond to needs-info
- request ID is visible in every important interaction
- requester and approver chats both resolve to the same request ID

#### Milestone: Lookup And Audit

Target outcome:

- the team can retrieve and inspect request history for real review and validation

Functionality:

- get request by ID
- show current review status
- show basic audit timeline
- summarize request state in plain language
- preserve evidence needed to reconstruct the reviewed revision

#### Milestone: Stabilization And Release Readiness

Target outcome:

- the initial release is testable and safe enough for internal use

Functionality:

- handle and hashtag parsing validation
- duplicate delivery and retry testing
- invalid-transition handling
- basic backup or export validation
- schema migration readiness for the chosen persistence backend
- happy-path test coverage
- smoke test for create, submit, review, and lookup

### Phase: Later Extensions

These items are valuable, but they should not block the first useful release.

#### Milestone: Shared Review Experience

- group-chat support
- optional approver reassignment
- reminder and escalation rules
- richer search and history filters

#### Milestone: AI Review Assistance

- before and after snapshot support
- diff analysis
- risk hints
- review checklist generation

#### Milestone: Rich Management Interface

- web dashboard
- richer request forms
- timeline explorer
- admin review tools

## Functional Requirements

### FR-1 Request Creation

- The agent must create a request from chat.
- The agent must derive or collect `target_label`, `change_from_summary`, `change_to_summary`, and `approver_handle` before submission.
- The agent must ask only for missing fields before creating the request.
- The agent must show a normalized request summary and require requester confirmation before submission.

### FR-2 Approver Targeting

- The agent must identify the approver from the message mention, handle, or hashtag.
- The agent must not submit a request when the approver is only a free-text display name.
- The agent must notify the tagged approver after request creation.
- The initial release may support only one approver per request.

### FR-3 Approval Decision

- The approver must be able to approve, reject, or request more info.
- The system must require a reason for rejection.
- The system should encourage a note for approval.

### FR-4 Auditability

- All request lifecycle events must be persisted.
- All decision events must be immutable.
- The system must store both structured state and chat evidence.
- The system must preserve the exact submitted revision that was approved, rejected, or cancelled.

### FR-5 Context Safety

- Every state-changing action must resolve to exactly one request.
- The system must prefer explicit request ID over inferred chat context.
- If multiple open requests match, the agent must ask the user to choose and must not guess.

### FR-6 Reliability And Idempotency

- The system must deduplicate repeated inbound chat events when the source platform retries delivery.
- Repeated approve, reject, cancel, or needs-info actions for the same source event must be treated as safe no-op replays.
- The system must prevent duplicate request creation from the same inbound source message.

### FR-7 Search And Lookup

- Users must be able to search by request ID.
- Broader search by target label, requester handle, approver handle, and time range should be limited to later milestones or participant-safe rules.
- The agent must summarize results in natural language.

### FR-8 Actor Identity Model

- The system must store requester and approver display names when available.
- The system must store requester and approver handles, usernames, or hashtags as channel-visible identifiers.
- The initial release must not depend on RBAC, directory lookup, or permission-access storage.
- The system must treat a resolvable approver handle or mention as mandatory for submission.

### FR-9 Notifications

- The system must notify the tagged approver on submission.
- The system must notify requester on decision.
- The system should support reminder and escalation policies in a later milestone.

### FR-10 Operational Safety

- The chosen persistence backend must be explicit before release deployment.
- The team must be able to back up or export `requests`, `audit_events`, and `request_conversations`.
- Schema changes should use a migration path if a SQL database is used.

## Recommended Initial Release Decisions

To keep the first release simple and correct, I recommend:

- Use a simple intake pattern such as "change from X to Y, ask @name to approve".
- Start with one lightweight request schema plus optional metadata.
- Require explicit approver actions through structured commands.
- Require requester confirmation before creating a real request.
- Treat `target_label`, `change_from_summary`, `change_to_summary`, and `approver_handle` as mandatory submit fields.
- Deduplicate inbound events before applying workflow state changes.
- Save every state-changing chat message reference into the audit timeline.
- Support one tagged approver per request in the initial release.
- Store names and handles instead of implementing RBAC.
- Use exact request ID lookup as the default non-participant retrieval path.
- Preserve request revisions so every approval decision points to one submitted snapshot.
- Defer execution-state modeling unless downstream execution is truly required.
- Defer before and after snapshot storage unless the chosen channel approach still leaves time for it.
- Keep AI generation advisory and never allow it to silently change workflow state.
- Choose one delivery channel first, then keep the workflow backend channel-agnostic.

## Open Questions

These should be confirmed before implementation starts:

1. Is the approver always included in the request message, or do we need a missing-approver prompt flow?
2. What mention format is exposed by the chosen channel adapter: `@username`, hashtag, or another resolvable identifier?
3. Is the final approved change executed by a human or by a downstream system?
4. Do we want broader search for non-participants later, or should that stay participant-only?
5. Do we need SLA timers and escalation in a later stage?
