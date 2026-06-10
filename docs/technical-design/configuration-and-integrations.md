# Configuration And Integrations

## Configuration Areas

The implementation should separate configuration into clear domains:

- Actor capture configuration
- Approver targeting configuration
- Object type configuration
- Delivery safety configuration
- Notification channel configuration
- AI review configuration
- Audit retention configuration

## Recommended Config Items

### Actor Capture

- display-name capture rules
- username, handle, or hashtag normalization
- channel-specific actor parsing rules

### Approver Targeting

- approver mention format
- how the bot detects approver tags in a message
- missing-approver prompt behavior when no resolvable approver is tagged
- whether any operator override exists outside the initial release

### Object Type Rules

- supported `target_object_type` values if needed
- minimum required fields for a valid request
- optional parsing hints for `change_from_summary` and `change_to_summary`

### Delivery Safety

- duplicate inbound message handling rules
- deduplication key shape per channel
- invalid transition behavior
- retry behavior for outbound notifications
- persistence mode selection

### Notification Channels

- direct chat channel
- optional email or secondary messaging integration later
- group thread channel in later stages

### AI Review

- enable or disable diff analysis
- prompt template version
- model selection
- confidence or risk thresholds if later introduced

### Audit Retention

- retention period
- export requirements
- immutable event policy

## Integration Areas

Recommended integration points:

- chat platform integration
- persistence store
- notification service
- target system or platform object service if needed later
- search or indexing service in later stages
- optional diff source provider

## External Integration Principles

- Keep business workflow inside the request service, not inside chat adapters.
- Treat chat as a channel, not the source of truth.
- Persist structured state before sending external notifications.
- Store references to external message IDs for traceability.
- Link actor-specific chat contexts back to one canonical request ID.
- Deduplicate inbound chat events before applying state transitions.
- Never treat free-form chat text alone as the authoritative approval decision.
- Do not implement RBAC or permission-directory integration in the initial release.

## Decisions Needed Before Implementation

These items have multiple valid choices and should be written down explicitly before build work starts:

| Decision | Options | Recommended Default |
|---|---|---|
| Approver mention format | `@username`, channel user ID mention, hashtag-style token | Use the most natively resolvable mention format in the chosen channel |
| Missing approver behavior | ask requester for a resolvable handle, operator override | Ask requester for a resolvable handle; do not auto-route |
| Persistence backend | SQLite, PostgreSQL | PostgreSQL for shared deployment; SQLite only for controlled single-instance use |
| Notification path | same bot DM only, add secondary notification path | same bot DM only |
| Read-only inspection surface | none, chat only, lightweight web view | chat only first |
