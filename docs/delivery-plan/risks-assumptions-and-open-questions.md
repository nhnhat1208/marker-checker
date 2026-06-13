# Risks, Assumptions, And Open Questions

## Purpose

This document captures the main risks and unresolved questions for the first release.

## Assumptions

- the first release uses one primary chat channel
- the requester can supply the approver during intake, either in the original message or a follow-up
- actor identity is represented by name plus channel-visible handle or user identifier
- lookup by request ID is enough for the first release
- the tool is intended for real internal use
- configuration uses YAML plus env overrides
- AI review assistance is not required for the first release

## Key Risks

### Risk: Over-Architecture Before The Workflow Is Proven

Impact:

- slower delivery
- more code than needed
- harder debugging

Mitigation:

- keep one channel adapter
- keep one persistence backend
- keep AI disabled
- avoid a second deployable component unless there is a real need

### Risk: Ambiguous Request Message

Impact:

- more clarification turns
- lower user confidence

Mitigation:

- define one preferred request sentence
- ask only for missing fields
- show normalized summary before confirmation

### Risk: Ambiguous Request Context

Impact:

- wrong request could be updated

Mitigation:

- prefer explicit request ID for state-changing actions
- do not guess if the context is unclear

### Risk: Google Sheets Operational Limits

Impact:

- slower writes at higher volume
- weak fit for concurrent multi-instance updates
- limited reporting and filtering

Mitigation:

- keep one runtime replica first
- keep write volume small in the first release
- keep persistence behind `WorkflowStore` so SQL migration stays possible later

### Risk: Credential Misconfiguration

Impact:

- runtime starts but cannot read or write the sheet
- deployment confusion between local and remote credential styles

Mitigation:

- support both local file and base64 env secret modes
- validate configuration on startup
- document the spreadsheet-sharing requirement clearly
- keep one clear config path: `runtime.yaml` locally and deploy env for remote overrides

### Risk: Weak Access Control

Impact:

- trust model stays soft
- lookup visibility is not deeply restricted

Mitigation:

- use the first release internally
- avoid sensitive content
- keep audit visible by request ID instead of broad search

## Open Questions

1. Should lookup remain exact `request_id` only, or should participant-safe search by target be added later?
2. At what usage point should persistence move from Google Sheets to a database?
3. Does the approver flow need a separate direct-message notification path, or is the current routed review flow enough for the first release?

Final release decisions should be tracked in [Scope And Channel Decision](../technical-design/scope-and-channel-decision.md) and [Implementation Plan](./implementation-plan.md), not duplicated here.
