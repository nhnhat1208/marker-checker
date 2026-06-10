# Workflow And Lifecycle

## Review Lifecycle States

Recommended `review_status` lifecycle:

1. `submitted`
2. `needs_info`
3. `approved`
4. `rejected`
5. `cancelled`

## State Transition Rules

- Agent creates the request in `submitted` once all required submit fields are present and the requester confirms the normalized summary.
- Approver can move the request to `needs_info`, `approved`, or `rejected`.
- Requester can respond to `needs_info`, confirm the revised summary, and return the request to `submitted`.
- Requester can move the request to `cancelled` while it is still `submitted` or `needs_info`.
- `approved` and `rejected` are terminal review states.
- `cancelled` is a terminal requester-controlled state.
- Each resubmission after `needs_info` must increment the request revision and store a fresh submitted snapshot.
- Every transition must create an audit event.

## Workflow Design Notes

These workflow assumptions make the design coherent and implementable:

- Request creation starts from one natural-language message.
- The preferred intake pattern is: "request change from ... to ..., ask @name to approve".
- The agent should only ask follow-up questions for missing fields.
- The minimum required submit fields are:
  - requester identity from the chat channel
  - target label
  - change-from summary
  - change-to summary
  - approver handle, mention, or other channel-resolvable identifier
- A free-text approver display name alone is not enough for submission.
- The initial release does not store RBAC or permission access for users.
- The initial release stores names and handles or hashtags exactly as seen in the channel.
- A real request record is created only after the requester confirms the normalized summary.
- Chat messages alone should not finalize approval unless the approver sends an explicit approval action.
- One request can be linked to more than one chat context, such as requester direct chat and approver direct chat.
- Explicit request ID wins when resolving context.
- If a message is a reply inside a request-linked thread, the thread request is the active context.
- If there is only one open request in the current chat for the actor, the agent may use it implicitly.
- If more than one open request matches, the agent must ask the user to choose and must not guess.

## Workflow: Request Intake And Submission

### Requester Creates And Submits A Request

Conversation flow:

1. Requester sends a message such as: "request change from X to Y, ask @alice to approve".
2. Agent extracts:
   - requester name and handle
   - target label or target summary
   - change-from summary
   - change-to summary
   - approver handle or hashtag
3. If any required submit field is missing, the agent asks only for the missing fields.
4. If the requester provides only a free-text approver name, the agent asks for a resolvable handle or mention before continuing.
5. When all required submit fields are available, the agent shows a normalized request summary and asks the requester to confirm.
6. If the requester corrects the summary, the agent updates it and asks for confirmation again.
7. Only after requester confirmation does the agent store the request and create the initial audit events.
8. Agent creates a request ID, sets `review_status` to `submitted`, stores revision `1` as the first submitted snapshot, and links the current conversation context to the request.
9. Agent notifies the approver and links the approver conversation context when the outbound message is sent.

Expected output from agent:

- A clean request summary.
- A request ID.
- The submitted revision number.
- Current `review_status`.
- Confirmation that the approver has been notified.

## Workflow: Approver Decision And Resolution

### Approver Reviews And Resolves The Request

Conversation flow:

1. Agent notifies the tagged approver in a direct thread or request-linked thread.
2. Agent presents:
   - Request summary
   - request ID
   - submitted revision
   - requester handle
   - target summary
   - change-from summary
   - change-to summary
3. Approver asks questions or requests clarification if needed.
4. Requester and approver can continue in linked request contexts, even if they are separate chats with the agent.
5. Approver decides:
   - Approve
   - Reject
   - Needs more info
6. If approver requests more info, the agent records the request, moves `review_status` to `needs_info`, and waits for requester updates.
7. If approver approves or rejects, the agent records the review action against the currently submitted revision, sets the terminal review state, and notifies the requester.

Expected output from agent:

- Clear decision record.
- Decision rationale.
- Updated `review_status`.
- Immutable audit event for the decision.

## Workflow: Needs-Info Revision Loop

### Requester Updates And Resubmits A Request

Conversation flow:

1. Approver moves the request to `needs_info`.
2. Agent tells the requester what information is missing and includes the request ID.
3. Requester sends the missing information in the same request context or with the explicit request ID.
4. Agent updates the request, increments the request revision, and shows a revised normalized summary.
5. Requester confirms the revised summary.
6. Agent stores a new submitted snapshot, moves `review_status` back to `submitted`, and re-notifies the approver.

Expected output from agent:

- Updated request summary.
- New submitted revision number.
- Updated `review_status`.
- Clear indication that the approver is reviewing the latest revision.

## Workflow: Request Cancellation

### Requester Cancels A Request

Conversation flow:

1. Requester refers to an active request by request ID or stable request context.
2. Agent checks that the request is still `submitted` or `needs_info`.
3. Agent asks for cancellation confirmation.
4. On confirmation, the agent moves the request to `cancelled`, stores the cancellation note if provided, and records the audit event.
5. Agent informs the approver if the request had already been sent for review.

Expected output from agent:

- Cancelled request ID.
- Final `review_status`.
- Cancellation note if one was provided.

## Workflow: Conversation Context Mapping And Safe Actions

One request may span more than one live chat context. The system should treat these as linked views of the same request rather than separate requests.

Recommended linked contexts:

- requester origin chat
- requester follow-up chat for `needs_info`
- approver review chat
- optional shared thread if the channel supports it

Each linked context should map back to the same canonical request ID.

The agent must resolve request context using this priority:

1. explicit request ID in the message
2. reply-to or thread-linked request context
3. request-to-conversation mapping for the current actor and current chat
4. exactly one open request in the current chat for that actor

If none of the above resolve to one request, the agent must:

- list matching request IDs with short summaries
- ask the user to choose one
- avoid taking any state-changing action until context is unambiguous

## Workflow: Lookup And Audit Retrieval

Lookup user examples:

- "Show request `REQ-1024`."
- "Summarize request `REQ-1024`."
- "Show the audit history for `REQ-1024`."

Agent behavior:

- Search request records and timeline events.
- Return a short summary plus links or references to full timeline entries.
- Show full details and full timeline only when the actor handle matches the requester or approver on that request.
- Allow exact request ID lookup for non-participants in the initial release.
- Restrict broad non-participant search by target, handle, or time range unless product rules are expanded later.
- Show summary-only details to non-participants by default:
  - request ID
  - target label
  - requester handle
  - approver handle
  - `review_status`
  - created and resolved timestamps
- Do not rely on RBAC in the initial release; use lightweight participant-based lookup behavior only.
