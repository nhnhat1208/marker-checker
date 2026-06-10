# Risks, Assumptions, And Open Questions

## Purpose

This document captures the main delivery assumptions, risks, and unresolved questions for the initial release.

## Assumptions

- the initial release will use one primary chat channel
- the requester includes the approver in the original message
- actor identity can be represented by display name plus handle or hashtag
- request lookup by request ID is enough for the first useful release
- the first release is intended for real internal use

## Key Risks

### Risk: Ambiguous Request Message

The requester may send a message that does not clearly include:

- target
- change from value
- change to value
- approver handle

Impact:

- extra clarification turns
- slower request creation

Mitigation:

- define one preferred request template
- ask only for missing fields
- show a normalized request summary and require requester confirmation

### Risk: Ambiguous Active Request Context

Users may have multiple open requests in the same chat and send messages like:

- "approve this"
- "update it"
- "cancel that one"

Impact:

- wrong request may be updated or resolved

Mitigation:

- prefer explicit request ID
- use reply-thread context when available
- ask the user to choose if more than one open request matches
- never guess for state-changing actions

### Risk: Approver Identity Ambiguity

Using only names and handles can be ambiguous if:

- users change display names
- two similar handles exist
- free-text names are used instead of explicit mentions

Impact:

- request may be routed to the wrong person

Mitigation:

- strongly prefer `@username` style mentions
- require a resolvable approver mention or handle before submission

### Risk: Duplicate Chat Event Delivery

Messaging platforms may retry webhook deliveries, button callbacks, or updates.

Impact:

- duplicate requests
- duplicate terminal decisions
- noisy or misleading audit history

Mitigation:

- deduplicate inbound events using stable source message identifiers
- make state transitions idempotent
- return safe no-op responses for replayed events

### Risk: Weak Access Control

The initial release intentionally avoids RBAC and directory integration.

Impact:

- weaker trust model
- lookup visibility is not tightly controlled

Mitigation:

- treat the initial release as internal or limited-scope
- avoid sensitive request content in the first release

### Risk: Persistence Durability

If the initial release uses local SQLite in the wrong environment, audit history may be fragile.

Impact:

- data loss after restart or redeploy

Mitigation:

- use PostgreSQL for shared internal deployment when possible
- if SQLite is used, keep deployment single-instance and validate backup or export procedures

## Open Questions

1. Is the approver always provided in the first request message?
2. What is the exact preferred request format for users?
3. Which resolvable mention format is mandatory in the chosen channel?
4. Does lookup need only `request_id`, or also handle and target search in the initial release?
5. Will the first release be an internally used working tool from day one?
6. Does downstream execution matter at all for the first release?
7. Should full audit timeline be visible only to requester and approver, or also to non-participants in limited cases?

## Decision Log Needed Before Build Starts

These are the multi-choice decisions that should be written down explicitly:

If no alternative is explicitly approved, use the recommended default.

| Decision | Options | Recommended Default |
|---|---|---|
| Primary channel | Telegram 1:1, Slack DM, internal chat | Telegram 1:1 |
| Persistence backend | PostgreSQL, SQLite | PostgreSQL for shared deployment; SQLite only for controlled single-instance use |
| Telegram transport | Long polling, webhook | Long polling |
| Revision storage | `audit_events` snapshots, `request_revisions` store | `audit_events` snapshots first |

## Review Checklist Before Build Starts

- confirm primary chat channel
- confirm preferred request message template
- confirm minimum required fields
- confirm persistence choice: PostgreSQL or controlled SQLite
- confirm inbound deduplication strategy
- confirm whether lookup is ID-only or includes simple search
- confirm whether the initial release is internal-use only or needs broader rollout readiness
- confirm backup or export procedure for audit data
