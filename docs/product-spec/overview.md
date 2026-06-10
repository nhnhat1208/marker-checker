# Product Overview

## Purpose

Build an AI agent that manages an approval workflow for changes on platform objects and keeps a full audit trail for future lookup and review.

Primary business goals:

- Help a requester create a simple change request for approval.
- Notify and assist an approver to approve or reject the request.
- Allow a `lookup user` to look up request status and history.
- Persist the whole process for audit, compliance, and later investigation.
- In a later AI review assistance stage, help approvers analyze the difference between `before` and `after` snapshots.

This specification is written as an implementation-oriented product spec for an AgentBase-based chat agent.

## Scope

### In Scope For Initial Release

- Lightweight multi-actor chat workflow using names and hashtags or handles.
- Request creation, review, approval, rejection, and status tracking.
- Persistent audit history.
- Exact request lookup and participant-safe history retrieval.
- Direct chat review conversations tied to one request.
- Agent-generated summaries and guidance for requester and approver.

### Out of Scope for Initial Release

- Direct mutation of production platform objects without human approval.
- Automatic approval without an approver decision.
- Complex policy engines such as risk scoring by department or region.
- Real-time integrations with every external system on day 1.
- Full legal/compliance policy authoring UI.

### Later Extension Scope

- Broader search across target labels, handles, status, and date ranges for non-participants.
- AI review assistance for object diffs before and after change.
- Richer request forms for object-specific workflows.

## Product Shape

This design makes the most sense as a chat-first approval assistant with these boundaries:

- One request represents one proposed change on one target object.
- One requester starts the request.
- One approver is tagged or mentioned in the request for the initial release.
- The initial release does not require permission access storage or RBAC.
- The initial release stores actor names and channel handles or hashtags instead of a formal identity directory.
- A valid request cannot be submitted until the agent has:
  - requester channel identity
  - target label
  - change-from summary
  - change-to summary
  - resolvable approver handle or mention
- If the requester provides only a free-text approver name, the agent must ask for a resolvable handle or mention before submission.
- Conversation happens primarily in direct chat, and workflow state changes happen through explicit approval actions.
- One request may be linked to multiple chat contexts, but request ID remains the canonical reference.
- The agent must show a normalized request summary and get requester confirmation before creating a real request.
- Every state-changing action must resolve to exactly one request.
- Non-participants get summary-only lookup by default, and exact request ID lookup is the safest initial-release path.
- Full request history is reserved for the requester or approver.
- Rich execution tracking and permission modeling are deferred.

## Users and Roles

### Requester

The actor who wants to create or modify something in the platform and needs approval.

Main actions:

- Send a change request in chat.
- Describe the change from one state to another state.
- Mention or tag the approver.
- Respond to approver questions.
- View final outcome.

### Approver

The actor who reviews the request and makes the approval decision.

Main actions:

- Receive notification from the agent.
- Inspect request details and change summary.
- Ask follow-up questions in the request thread.
- Approve or reject.
- Provide rejection reason or approval note.

### Lookup User

The actor who is not directly involved in approval but wants to look up status or history.

Main actions:

- Look up requests by request ID.
- View audit summary by default, and full timeline when the user is the requester or approver on that request.
- Ask the agent for a summary of what happened.

### Agent

The AI workflow assistant and orchestration layer.

Main responsibilities:

- Collect missing information from requester.
- Normalize request data into a structured format.
- Require a resolvable approver handle before submission.
- Route the request to the tagged approver.
- Keep all actions and messages in an audit timeline.
- Help both sides understand the request.
- In a later AI review assistance stage, analyze diffs and generate review insights.

## Success Criteria

### Core Approval Workflow

- A requester can create a request entirely through chat.
- The requester confirms the normalized request summary before the request is submitted.
- A valid request cannot be submitted without a target label, change-from summary, change-to summary, and resolvable approver handle.
- An approver can approve, reject, or request more info through chat.
- The agent stays stable even when multiple requests are active by requiring explicit request context resolution.
- A lookup user can look up request history by exact request ID without seeing full participant details by default.
- Every step is recorded in an audit trail.

### Later-Stage AI Review Assistance

- The agent can explain what changed between before and after snapshots.
- The approver gets useful risk-aware review assistance.
- AI analysis improves review speed without reducing audit quality.
