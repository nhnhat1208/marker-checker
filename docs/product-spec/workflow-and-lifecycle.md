# Workflow And Lifecycle

## Review States

The first release uses these states:

1. `submitted`
2. `needs_info`
3. `approved`
4. `rejected`
5. `cancelled`

## Transition Rules

- requester creates a real request only after confirmation
- approver can move `submitted` to `approved`, `rejected`, or `needs_info`
- requester can resubmit after `needs_info`
- requester can cancel while the request is still active
- `approved`, `rejected`, and `cancelled` are terminal
- every transition creates an audit event

## Main Workflow

### 1. Request Intake

1. requester sends a message
2. agent extracts:
   - `target_label`
   - `change_from_summary`
   - `change_to_summary`
   - `approver_handle`
3. if fields are missing, agent asks only for missing data
4. agent shows a normalized summary
5. requester confirms with `/confirm`
6. request is created in `submitted`

### 2. Approver Review

1. approver receives the request summary
2. approver can:
   - approve
   - reject
   - request more info
   - cancel where allowed
3. agent records the decision and updates status

### 3. Needs-Info Loop

1. approver moves request to `needs_info`
2. requester sends updated details
3. agent shows the revised summary
4. requester confirms again
5. request goes back to `submitted`

### 4. Lookup

- `status` returns current request summary
- `history` returns the audit timeline
- request ID is the safest lookup key

## Interaction Rules

- natural-language chat is the primary UX
- slash commands are shortcuts, not the only path
- explicit request ID is preferred for state-changing actions
- the agent must not guess when request context is ambiguous
