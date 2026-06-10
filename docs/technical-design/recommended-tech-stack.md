# Recommended Tech Stack

## Purpose

This document recommends a practical tech stack for the initial release.

The recommendation is optimized for:

- a simple but correct internal-use release
- low delivery risk
- easy Telegram integration
- simple persistence for request and audit history

## Recommended Stack

### Application Model

- custom Python service
- channel-agnostic workflow backend
- Telegram 1:1 bot as the first adapter

### Runtime

- Python `3.11`

Why:

- fast to build in the current repo context
- strong library support for bots and APIs
- easy to ship as a small service

### Web Or Health Layer

- `FastAPI`

Why:

- simple health endpoint
- easy internal endpoint support later
- good fit for a small service

### Telegram Adapter

- `python-telegram-bot`

Recommended initial mode:

- long polling first

Why:

- faster setup than webhook infrastructure
- lower integration friction for an early release
- enough for an internal first release

### Persistence

- `PostgreSQL` as the recommended default for a shared internal deployment
- `SQLite` only if deployment is controlled, single-instance, and backup expectations are modest

Why:

- PostgreSQL is safer for an audit-oriented tool that should survive restarts and redeploys
- SQLite is still acceptable for a tightly controlled first environment
- the data model is still small enough to keep operations manageable

### Data Access Layer

- `SQLAlchemy`

Why:

- mature and flexible
- easy to start small and upgrade later
- works with both SQLite and PostgreSQL

### Logging

- structured application logs using standard Python logging

Why:

- enough for first-release debugging
- no need for a heavy observability stack at the start

## Minimal Stack Shape

Recommended initial stack summary:

- Python `3.11`
- `FastAPI`
- `python-telegram-bot`
- `SQLAlchemy`
- `PostgreSQL` for shared deployment, `SQLite` only for controlled single-instance deployment

## Service Boundaries

### Keep In The Same Service For The Initial Release

- message parsing
- request creation
- approver notification
- approval or rejection actions
- lookup by request ID
- audit event storage

### Defer To Later

- separate web frontend
- separate AI diff-analysis service
- identity directory integration
- permission or RBAC layer

## Schema Recommendation

Start with only these persistent tables or collections:

- `requests`
- `audit_events`
- `request_conversations`

Choose one revision persistence approach before implementation:

- keep revision snapshots inside `audit_events`
- add a dedicated `request_revisions` store

Optional later:

- `ai_analysis_artifacts`

## Rejected Or Deferred Stack Choices

### Full Web App First

Rejected for the initial release because:

- higher delivery risk
- more UI work than the first release needs

### Group Chat First

Rejected for the initial release because:

- more ambiguity around actor intent
- harder audit capture

### RBAC And Identity Directory

Rejected for the initial release because:

- not required for the simplified handle-based flow
- too much integration work for the first release

## Decisions Needed Before Implementation

If no explicit alternative is recorded, implementation should follow the recommended default.

| Decision | Options | Recommended Default |
|---|---|---|
| Persistence backend | PostgreSQL, SQLite | PostgreSQL if any shared deployment exists; SQLite only for controlled single-instance use |
| Revision persistence | `audit_events` snapshots, `request_revisions` table | `audit_events` snapshots first |
| Telegram transport | Long polling, webhook | Long polling first |

## Upgrade Path

If the initial release works, the next technical upgrades should be:

1. if the first deployment started with SQLite, move persistence to PostgreSQL
2. add a read-only web request viewer
3. add group-chat support
4. add AI diff analysis
5. add stronger identity and authorization
