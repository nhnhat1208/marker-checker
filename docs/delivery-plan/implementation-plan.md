# Implementation Plan

This document defines scope, milestones, and key decisions for the first useful release.

For AgentBase setup and deployment sequence, use [AgentBase Execution Plan](./agentbase-execution-plan.md) together with this plan.

## Delivery Mindset

Build a simple but correct tool, not a throwaway demo.

That means:

- keep the workflow narrow
- keep state rules explicit
- avoid extra architecture until the core approval flow proves useful

The locked first-release decisions are maintained in [Scope And Channel Decision](../technical-design/scope-and-channel-decision.md). This plan assumes those decisions are already final.

## Initial Release Goal

Deliver one working workflow where:

- requester sends a simple change request
- approver reviews and resolves it
- lookup by request ID works
- audit history is persisted and readable

## Scope

### Must Build

- simple request intake from one message
- requester confirmation before submission
- approver-handle validation
- `runtime.yaml` as the primary configuration source
- `.agentbase/deploy.env` for deploy overrides
- Google Sheets persistence
- approve, reject, needs-info, cancel
- request lookup by request ID
- audit history by request ID
- one explicit state transition map
- one channel adapter

### Defer

- AI diff analysis
- group chat workflow
- web dashboard
- RBAC
- reminder automation
- multiple channel adapters
- separate workers

## Milestones

### Milestone 1: Core Request Flow

Target result:

- requester can submit a request
- request is persisted
- audit events are created

Main functionality:

- parse request message
- normalize request summary
- require `/confirm`
- create request record
- create initial audit events

### Milestone 2: Review Flow

Target result:

- approver can resolve the request from Telegram

Main functionality:

- approve
- reject
- request more info
- cancel
- resubmit after needs-info

### Milestone 3: Lookup And Audit

Target result:

- request state and history are easy to inspect

Main functionality:

- `/status REQ-...`
- `/history REQ-...`
- consistent request summary response

### Milestone 4: Stabilization

Target result:

- tool is reliable enough for small internal use

Main functionality:

- config validation
- worksheet creation validation
- restart behavior validation
- state transition guard validation
- deploy verification

## Functional Requirements

### FR-1 Request Creation

- The agent must create a request from chat.
- The agent must derive or collect `target_label`, `change_from_summary`, `change_to_summary`, and `approver_handle`.
- The agent must require requester confirmation before real submission.

### FR-2 Approver Targeting

- The agent must identify the approver from a resolvable handle, mention, or other channel-visible identifier.
- The agent must not submit a request when the approver is only a free-text name.
- The initial release supports one approver per request.

### FR-3 Approval Actions

- The approver must be able to approve, reject, request more info, or cancel where allowed.
- Rejection must include a reason if that rule is enabled.

### FR-4 Audit And Lookup

- Every important workflow action must create an audit event.
- Lookup by request ID must return current state.
- History by request ID must return the event timeline.

## Execution Checklist

Use this checklist during implementation and release preparation.

### Phase 0: Baseline Alignment

- [ ] Review the locked first-release scope in [Scope And Channel Decision](../technical-design/scope-and-channel-decision.md)
- [ ] Verify the team is still aligned on `Telegram 1:1` as the first channel
- [ ] Verify the team is still aligned on `Google Sheets` as the first persistence backend
- [ ] Verify one approver per request is acceptable for the first release
- [ ] Verify the first release remains internal-use only unless stronger access control is added

### Phase 1: External Setup

AgentBase:

- [ ] Confirm IAM credentials work
- [ ] Confirm container registry access
- [ ] Confirm runtime deployment permission
- [ ] Confirm monitoring access

Telegram:

- [ ] Create Telegram bot
- [ ] Store bot token securely
- [ ] Confirm approver mention format

Google Sheets:

- [ ] Create shared spreadsheet
- [ ] Create or reuse service account
- [ ] Share spreadsheet with service-account email
- [ ] Record spreadsheet ID
- [ ] Decide credential delivery mode: local file or base64 env secret

### Phase 2: Project Scaffold

- [ ] Add runtime config loader
- [ ] Add adapter, orchestrator, services, and persistence packages
- [ ] Add `runtime.example.yaml`
- [ ] Add local `runtime.yaml`
- [ ] Add `.agentbase/deploy.env` for deploy overrides
- [ ] Confirm `runtime.yaml` is ignored by git

### Phase 3: Persistence

- [ ] Define `WorkflowStore`
- [ ] Implement `GoogleSheetsWorkflowStore`
- [ ] Auto-create `requests`
- [ ] Auto-create `audit_events`
- [ ] Auto-create `request_conversations`
- [ ] Confirm request rows can be created and updated
- [ ] Confirm audit rows append in correct order

### Phase 4: Core Workflow

- [ ] Parse simple request message
- [ ] Extract `target_label`
- [ ] Extract `change_from_summary`
- [ ] Extract `change_to_summary`
- [ ] Extract `approver_handle`
- [ ] Show normalized request summary
- [ ] Require requester confirmation
- [ ] Create request only after confirmation
- [ ] Record initial audit events
- [ ] Support approve action
- [ ] Support reject action
- [ ] Support needs-info action
- [ ] Support cancel action
- [ ] Support resubmission after needs-info
- [ ] Support `/status REQ-...`
- [ ] Support `/history REQ-...`

### Phase 5: Workflow Safety

- [ ] Implement explicit transition map
- [ ] Guard invalid transitions
- [ ] Keep storage detail out of request and audit services
- [ ] Keep Telegram SDK detail out of workflow services
- [ ] Resolve state-changing actions by explicit request ID
- [ ] Avoid guessing request context when ambiguous

### Phase 6: Local Validation

- [ ] Start runtime locally
- [ ] Verify Google Sheets connection
- [ ] Verify worksheet auto-creation
- [ ] Test create request flow
- [ ] Test approve flow
- [ ] Test reject flow
- [ ] Test needs-info and resubmit flow
- [ ] Test cancel flow
- [ ] Test lookup flow
- [ ] Restart runtime and verify old requests still load

### Phase 7: Build And Deploy

- [ ] Confirm Dockerfile
- [ ] Confirm `.dockerignore`
- [ ] Build image locally
- [ ] Push image to AgentBase managed registry
- [ ] Prepare deploy override variables
- [ ] Deploy one `Custom Agent` runtime
- [ ] Use one replica first
- [ ] Confirm runtime becomes `ACTIVE`

### Phase 8: Release Verification

- [ ] Confirm health endpoint responds
- [ ] Confirm Telegram end-to-end flow works in deployed runtime
- [ ] Confirm spreadsheet rows are written correctly
- [ ] Confirm logs are visible in AgentBase Monitor
- [ ] Confirm audit history remains readable after redeploy

Later changes should be recorded in [Scope And Channel Decision](../technical-design/scope-and-channel-decision.md) when they become active scope.
