# Chat And Review Capabilities

## Required Chat Modes

- `requester <-> agent`
- `approver <-> agent`
- `lookup user <-> agent` for lookup
- group-chat support is optional and deferred from the initial release

## Initial Release Chat Requirements

- One request has one canonical request ID.
- Agent should accept one natural-language intake message for request creation.
- Agent should derive requester handle from the channel identity when possible.
- Request submission requires `target_label`, `change_from_summary`, `change_to_summary`, and a resolvable `approver_handle`.
- Requester and approver can continue in linked request contexts, even when they are separate chats with the agent.
- Agent must show a normalized summary and request confirmation before submitting a request.
- State-changing actions must resolve exactly one request.
- Agent summarizes long conversations when needed.
- The final decision must be captured as an explicit approval action, not inferred only from chat text.

## Stable Context Rules

- Natural-language request creation is the primary UX.
- Slash commands are optional shortcuts, not the only supported path.
- For status-changing actions, explicit request ID is preferred.
- If the actor replies inside a request-linked thread, the agent should use that request context.
- If the channel uses separate requester and approver chats, both chats should be linked back to the same request ID.
- If multiple open requests could match, the agent must ask the user to choose and must not guess.
- After every state-changing action, the agent should echo:
  - request ID
  - current `review_status`
  - active revision when relevant

## Recommended Conversation Features

- `/request` as an optional shortcut to create a request from a simple message template.
- `/status` to show current workflow state.
- `/history` to show timeline.
- `/approve`, `/reject`, `/need-info` as explicit commands or structured actions.
- `/cancel` to cancel an active request before terminal resolution.
- `/summary` to summarize the current request discussion.

## Requester-Facing Behavior

- Accept a message like "change from X to Y, ask @alice to approve".
- Ask only for missing fields.
- Transform unstructured text into a lightweight structured request.
- If the requester gives only an approver display name, ask for a resolvable handle or mention before submission.
- Show the normalized request summary before submission.
- Make clear that the request has been submitted and who was tagged as approver.
- Explain current status clearly.

## Approver-Facing Behavior

- Present concise review packets.
- Highlight missing data.
- Make decision actions explicit and auditable.
- Keep the approver focused on the request ID and change summary.
- Encourage explicit approve or reject actions rather than vague replies like "looks good".

## Lookup Behavior

- Return exact request ID matches first.
- Offer broader filters only when the product explicitly allows them.
- Summarize using stored request data and audit events.
- Show full details only to the requester or approver on that request.
- Show summary-only details to non-participants by default.
- In the initial release, broad non-participant search by target, handle, or time range should be restricted or deferred.

## Later-Stage AI Review Assistance

This capability is not part of the initial release and depends on additional request fields defined in the later-stage extension of the data model.

### Goals

- Explain what changed in plain language.
- Highlight risky changes.
- Detect missing fields or suspicious modifications.
- Help approver focus attention without replacing human decision-making.

### Inputs

- `before_snapshot_ref`
- `after_snapshot_ref`
- `snapshot_schema_version`
- `change_type`
- object metadata
- policy or review guidance if available

### Outputs

- Short change summary
- Structured field-level diff
- Risk hints
- Questions the approver may want to ask
- Suggested approval checklist

### Guardrails

- AI analysis is advisory only.
- Final decision remains with approver.
- AI output must be stored as an analyzable artifact with version and timestamp.
