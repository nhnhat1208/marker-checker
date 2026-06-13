# Data Model And Audit

## Required Submit Fields

A real request is created only when these fields exist:

- `requester_handle`
- `target_label`
- `change_from_summary`
- `change_to_summary`
- `approver_handle`

Optional fields:

- `target_object_type`
- `business_reason`

## Request Record

Main request fields:

- `request_id`
- `request_text`
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
- `created_at`
- `updated_at`

Additional terminal fields are stored for approval, rejection, and cancellation details.

## Audit Events

The audit timeline should capture:

- `request_submitted`
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
- `actor_handle`
- `occurred_at`
- `summary`
- `event_payload`

## Logical Record Sets

The first release uses three logical record sets:

- `requests`
- `audit_events`
- `request_conversations`

## Revision Rule

When a requester updates a request after `needs_info`:

1. increment the revision
2. show the revised summary
3. require confirmation again
4. store the new submitted revision in audit history
