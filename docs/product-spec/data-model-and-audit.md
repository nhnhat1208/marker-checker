# Data Model And Audit

## Initial Release Change Model

For the initial release, the agent can store a lightweight human-readable change description instead of a strict object contract.

The agent should treat request creation as a two-step process:

- intake and normalization in chat
- real request creation only after requester confirmation

The audit timeline begins only after the real request is created.

## Minimum Required Submit Fields

The agent should not create a real request until these fields are available:

| Field | Required | Notes |
|---|---|---|
| `requester_handle` | Yes | Derived from channel identity when possible |
| `target_label` | Yes | Human-readable object or target reference |
| `change_from_summary` | Yes | Short description of the current state |
| `change_to_summary` | Yes | Short description of the proposed state |
| `approver_handle` | Yes | Must be resolvable through the chosen chat channel |
| `target_object_type` | No | Optional classification |
| `business_reason` | No | Optional explanation |
| `request_tags` | No | Optional labels if the product adds them later |

Current lightweight change summary fields:

| Field | Description |
|---|---|
| `target_label` | Human-readable target name or identifier |
| `target_object_type` | Optional category of target object |
| `change_from_summary` | Short summary of the current state |
| `change_to_summary` | Short summary of the proposed state |

## Current First-Release Request Model

| Field | Description |
|---|---|
| `request_id` | Unique request identifier |
| `request_text` | Original requester message |
| `requester_name` | Requester display name from the chat channel |
| `requester_handle` | Requester handle or user identifier from the chat channel |
| `approver_name` | Approver display name if available |
| `approver_handle` | Approver handle or user identifier from the chat channel |
| `target_label` | Human-readable target name or identifier |
| `target_object_type` | Optional target object type |
| `change_from_summary` | Short summary of the current state |
| `change_to_summary` | Short summary of the proposed state |
| `business_reason` | Optional explanation for why the change is needed |
| `review_status` | Submitted, needs_info, approved, rejected, cancelled |
| `current_revision` | Latest normalized request revision number |
| `last_submitted_revision` | Revision number currently under review |
| `last_submitted_at` | Timestamp of the latest submitted revision |
| `created_at` | Request creation time |
| `updated_at` | Last update time |
| `resolved_at` | Time the review reached approved or rejected |
| `resolution_note` | Final approval note or rejection reason |
| `resolved_by_name` | Approver display name that made the terminal decision |
| `resolved_by_handle` | Approver handle that made the terminal decision |
| `cancelled_at` | Time the request was cancelled, if applicable |
| `cancelled_by_handle` | Handle that cancelled the request |
| `cancellation_note` | Optional reason for cancellation |
| `origin_channel_id` | Channel where the request was first created |
| `origin_thread_id` | Thread ID if the origin channel supports threads |
| `origin_message_id` | Source message reference for the initial request intake |

## Audit Timeline

Audit users need more than status. They need sequence and evidence.

The first-release audit timeline should capture:

- `request_submitted`
- `approver_notified`
- `needs_info_requested`
- `request_resubmitted`
- `decision_recorded`
- `request_cancelled`
- `lookup_performed`

## Audit Event Model

Every audit event should store:

| Field | Description |
|---|---|
| `event_id` | Unique event ID |
| `event_sequence` | Monotonic sequence number within one request timeline |
| `request_id` | Parent request |
| `event_type` | Canonical event type such as `request_submitted`, `request_resubmitted`, `needs_info_requested`, `decision_recorded`, or `request_cancelled` |
| `actor_name` | Display name of the actor who triggered it |
| `actor_handle` | Handle or user identifier of the actor who triggered it |
| `actor_kind` | Requester, approver, agent, or system |
| `request_revision` | Revision number associated with the event, if applicable |
| `occurred_at` | Event time |
| `summary` | Human-readable event summary |
| `event_payload` | Structured event details including the normalized request snapshot for submitted, approved, rejected, and cancelled events |
| `source_channel` | Direct chat, group chat, system callback |
| `thread_id` | Canonical thread or source thread identifier |
| `source_message_id` | External message reference if triggered from chat |

## Current Shared Record Sets

Use these logical record sets in the first release:

- `requests`
- `audit_events`
- `request_conversations`

## Request Conversation Mapping

Because one request may span more than one chat context, the system should map request IDs to actor-specific conversation contexts.

Recommended `request_conversations` fields:

| Field | Description |
|---|---|
| `request_id` | Parent request |
| `actor_handle` | Requester or approver handle for this linked context |
| `conversation_role` | Origin, requester_followup, approver_review, or shared_thread |
| `channel_id` | Channel or DM identifier |
| `thread_id` | Thread identifier if the channel supports threads |
| `conversation_id` | Fallback conversation identifier when threads do not exist |
| `linked_at` | Time the mapping was created |
| `last_seen_at` | Time of the last message seen in this context |

## Request Revision Model

Each time the requester changes request content after `needs_info`, the system should:

1. increment `current_revision`
2. show the revised normalized summary to the requester
3. require requester confirmation before resubmission
4. set `last_submitted_revision` to the confirmed revision
5. store the submitted revision snapshot in audit history

This ensures the approver decision can always be traced to the exact submitted content.

## Later AI Extension

If AI review assistance becomes active scope later, extend the request model and add AI artifact storage in [AI Review Assistance](../future/ai-review-assistance.md) rather than expanding the first-release model here.
