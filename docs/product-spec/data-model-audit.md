# Data Model Audit

## Required Fields

For the standard chat-driven submission flow, a complete request draft usually includes:

- `requester_handle`
- `target_label`
- `change_from_summary`
- `change_to_summary`
- `approver_handle`

Optional fields:

- `target_object_type`
- `business_reason`
- `structured_payload_json`
- `impact_note`

## Structured Web Exception

The web structured flow can persist a request without an approver when the payload itself is valuable and review can be completed later in the web UI. In that case:

- the request is saved with an empty `approver_handle`
- the raw structured payload is preserved
- notification is skipped until an approver is available

## Request Record

Main request fields include:

- `request_id`
- `request_text`
- `structured_payload_json`
- `impact_note`
- `requester_name`
- `requester_handle`
- `approver_name`
- `approver_handle`
- `target_label`
- `target_object_type`
- `change_from_summary`
- `change_to_summary`
- `business_reason`
- `review_status`
- `current_revision`
- `last_submitted_revision`
- `last_submitted_at`
- `created_at`
- `updated_at`
- `origin_channel_id`
- `origin_thread_id`
- `origin_message_id`

Resolution-related fields are also stored for approval, rejection, and cancellation outcomes.

## Audit Events

Current audit event types include:

- `request_submitted`
- `missing_fields_requested`
- `request_draft_updated`
- `approver_notified`
- `needs_info_requested`
- `request_resubmitted`
- `decision_recorded`
- `request_cancelled`
- `lookup_performed`

Each audit event stores:

- `event_id`
- `event_sequence`
- `request_id`
- `event_type`
- `actor_name`
- `actor_handle`
- `actor_kind`
- `request_revision`
- `occurred_at`
- `summary`
- `event_payload`
- `source_channel`
- `thread_id`
- `source_message_id`

## Logical Record Sets

The persistence layer currently manages these logical record sets:

- `requests`
- `audit_events`
- `request_conversations`
- `chat_registry`
- `pending_drafts`
- `pending_resubmit`
- `user_profiles` for Google-authenticated web users in the Postgres backend

## Revision Rule

When a requester updates a request after `needs_info`:

1. the revision is incremented
2. the updated request is resubmitted
3. the latest submitted revision is tracked separately from the working revision
4. the audit trail captures the transition and revision context
