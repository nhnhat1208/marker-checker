# Product Overview

## Purpose

Build a simple chat-first approval tool.

The tool helps:

- a requester create a change request
- an approver review and resolve it
- a lookup user check status and audit history

## Initial Scope

In scope:

- Telegram and API request intake
- requester confirmation before submission
- one approver per request
- approve, reject, need-info, cancel
- lookup by exact request ID
- audit trail in Google Sheets

Out of scope:

- RBAC
- web UI
- group-chat workflow
- direct mutation of external platform objects
- AI diff analysis

## Product Boundaries

- one request represents one proposed change
- one requester starts the request
- one approver is identified by a resolvable handle
- a request is created only after requester confirmation
- every state-changing action must resolve to exactly one request
- request ID is the canonical reference

## Roles

### Requester

- sends the change request
- confirms the normalized summary
- answers follow-up questions

### Approver

- reviews the request
- approves, rejects, asks for more info, or cancels where allowed

### Lookup User

- checks request status or history by request ID

### Agent

- collects missing fields
- normalizes the request
- manages workflow transitions
- stores audit history

## Success Criteria

- requester can create a request from chat
- approver can resolve the request from chat
- lookup by request ID works
- audit history clearly explains what happened
