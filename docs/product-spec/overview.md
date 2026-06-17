# Product Overview

## Purpose

Build a simple chat-first approval tool for small change requests.

## Scope

In scope:

- request intake from Telegram, web chat, or API invocation
- requester confirmation before submission
- one requester and one approver per request
- approve, reject, need-info, cancel
- lookup by request ID, plus lightweight search and personal request lists
- audit trail for every state-changing action
- PostgreSQL as the default store, with Google Sheets as a legacy fallback
- optional LLM assistance for parsing and wording

Out of scope:

- RBAC or admin console
- multi-step approval chains
- file attachments
- direct mutation of external platform objects
- AI making final approval decisions

## Product Boundaries

- one request represents one proposed change
- a request is created only after requester confirmation
- one approver is identified by a resolvable handle
- every state-changing action must resolve to exactly one request
- request ID is the canonical reference

## Roles

### Requester

- starts a request
- confirms the normalized draft
- answers follow-up questions after `needs_info`

### Approver

- reviews the submitted request
- approves, rejects, requests more info, or cancels where allowed

### Lookup User

- checks status, history, search results, or personal request lists

### Agent

- collects missing fields
- normalizes the request
- manages workflow transitions
- stores audit history

## Success Criteria

- a requester can create a request from chat
- an approver can resolve it from chat
- request lookup and lightweight query flows work reliably
- audit history clearly explains what happened
