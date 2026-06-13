# Scope And Channel Decision

## Purpose

This document records the locked scope and channel decisions for the initial release and preserves the comparison that led to them.

The goal is not to choose the biggest design. The goal is to choose the approach most likely to produce a simple, correct, and useful first release.

This is the primary decision record for the initial release. Other technical and delivery docs should follow this file instead of redefining the same choices.

## Decision Summary

| Decision ID | Topic | Chosen Decision | Status |
|---|---|---|---|
| `DEC-001` | Delivery target | Build one simple but correct end-to-end first release | Final |
| `DEC-002` | Primary channel | Use Telegram 1:1 as the first user-facing channel | Final |
| `DEC-003` | Architecture | Keep a channel-agnostic workflow backend behind the bot | Final |
| `DEC-004` | Group chat | Defer full group-review workflow until after the initial release | Final |
| `DEC-005` | Web UI | Defer full web UI and keep inspection in chat first | Final |
| `DEC-006` | AI review assistance | Defer diff analysis until the core workflow is already stable | Final |
| `DEC-007` | Identity model | Store actor names and channel-visible handles only; do not build RBAC in the initial release | Final |
| `DEC-008` | Intake pattern | Use one simple natural-language request message as the primary intake pattern | Final |

## Evaluation Criteria

The approaches are compared using these criteria:

- speed to first useful release
- delivery risk for the initial implementation
- fit for requester and approver workflow
- auditability and explicit decision capture
- implementation complexity
- future extensibility

## Approach Options

### Option: Web-Based Workflow

Description:

- Build a web app where requester and approver interact with the workflow directly.
- Agent is embedded into the web interface or exposed as an assistant panel.

What it is good at:

- strongest control over forms and validations
- best surface for rich timelines and future diff visualization
- easiest place to show structured request details clearly

What makes it expensive:

- frontend work, session handling, and richer UI expectations
- more work for forms, validation, and review screens
- more polish expected from users once a web UI exists

Estimated effort:

- minimal internal prototype: medium
- realistic usable first release with decent UX: high

Risk level:

- medium to high

Verdict:

- not the best primary path unless a web shell already exists and only a thin workflow layer is needed

### Option: Telegram 1:1 Bot

Description:

- Requester and approver interact with the agent in direct Telegram chats.
- The bot manages request creation, review prompts, and lookup commands.

What it is good at:

- fastest path to a working conversational first release
- simple actor model using names and handles
- easy to keep request actions explicit through commands or buttons
- low UI overhead

What makes it constrained:

- lookup and history views are more compact than a web UI
- complex forms are awkward in chat
- large audit timelines are harder to browse

Estimated effort:

- low to medium

Risk level:

- low to medium

Verdict:

- best fit for the initial release

### Option: Telegram Group Assistant

Description:

- Add the agent to a group where requester and approver both interact in a shared conversation.

What it is good at:

- shared context between requester and approver
- useful for collaborative review once workflow is stable
- closer to the long-term review-assistant vision

What makes it risky:

- harder to distinguish commands from casual conversation
- more ambiguity around which mentioned person is the real approver
- harder audit mapping from noisy thread activity
- higher chance of false or accidental workflow changes

Estimated effort:

- medium to high

Risk level:

- medium to high

Verdict:

- attractive conceptually, but too risky as the first and only release path

### Option: Hybrid Telegram 1:1 Plus Lightweight Read-Only Web View

Description:

- Use Telegram 1:1 for workflow actions.
- Add a small read-only web page or internal page for viewing request detail and audit timeline.

What it is good at:

- keeps the fastest chat workflow
- gives a cleaner place to inspect request details
- improves inspection and internal reviews

What makes it risky:

- still introduces web work
- can expand in scope very quickly if editing is added

Estimated effort:

- medium

Risk level:

- medium

Verdict:

- good fallback if the team strongly needs a cleaner read-only inspection surface, but only if the web part stays read-only

### Option: Backend API Plus Internal CLI Or Admin Console

Description:

- Build only the workflow engine and let internal users trigger it through scripts, CLI, or a simple admin endpoint.

What it is good at:

- fastest path to validate backend logic
- easiest way to prove workflow correctness and audit model

What makes it weak:

- does not satisfy the chat-first user experience well
- weak user-facing experience for requester and approver interaction

Estimated effort:

- low

Risk level:

- low

Verdict:

- useful as a fallback engineering prototype, but not a strong product first release

## Comparison Summary

| Approach | Delivery Speed | Delivery Risk | Workflow Fit | Audit Fit | Recommendation |
|---|---|---|---|---|---|
| Web-based workflow | Medium | High | High | High | Later |
| Telegram 1:1 bot | High | Low-Medium | High | High | Best Initial Release |
| Telegram group assistant | Medium | High | Medium-High | Medium | Later |
| Telegram 1:1 + read-only web | Medium | Medium | High | High | Optional |
| Backend API only | Very High | Low | Low | High | Fallback only |

## Locked Initial Release Path

### Final Direction

Build:

- a channel-agnostic workflow backend
- a Telegram 1:1 bot as the primary interface
- a simple intake pattern such as "change from X to Y, ask @name to approve"
- request lookup by request ID
- basic audit timeline retrieval

Defer:

- group chat review workflow
- full web application
- AI diff analysis

### Why This Is The Best Fit

- It gives the fastest usable conversational experience.
- It keeps approval actions explicit and auditable.
- It fits a lightweight handle-based identity model.
- It avoids frontend scope explosion.
- It still preserves a clean path to add web or group-chat adapters later.

## Features To Defer From The Initial Release

- shared group-chat resolution flow
- multi-approver workflow
- SLA automation
- advanced search filters
- attachments
- execution pipeline integration
- AI-generated diff analysis
- rich web dashboard
- RBAC and permission-directory integration

## Conditions That Would Change The Recommendation

Choose a web-first first release instead if:

- a web shell already exists
- structured request forms matter more than conversational speed

Choose group-chat-first only if:

- shared discussion in one room is the main product value
- the team accepts higher delivery risk
- approval actions can still be captured explicitly and safely

Choose hybrid Telegram plus read-only web if:

- the team needs a cleaner audit view
- approvers need more structured read-only context
- the team can protect the web scope from turning into a full product
