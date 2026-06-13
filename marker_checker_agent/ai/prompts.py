from __future__ import annotations


REQUEST_PARSE_PROMPT_VERSION = "request-parse-v1"

REQUEST_PARSE_SYSTEM_PROMPT = """
Extract a marker-checker approval request into JSON only.
Keys: target_label, change_from_summary, change_to_summary, approver_handle, guidance_message.
Rules: approver_handle must start with @ when present. Unknown values must be empty strings.
guidance_message should be short and only ask for missing fields.
""".strip()

REQUEST_CLARIFICATION_SYSTEM_PROMPT = """
Write one short clarification message for a marker-checker approval workflow.
Be concise, natural, and action-oriented.
Do not invent missing values.
Use plain text only. Do not use Markdown, bullet points, or any special formatting.
""".strip()

REQUEST_CONFIRMATION_SYSTEM_PROMPT = """
Write one short confirmation message for a marker-checker approval workflow.
Be concise and easy to verify.
End by telling the user to reply with /confirm.
Use plain text only. Do not use Markdown, bullet points, or any special formatting.
""".strip()

REQUEST_STATUS_SUMMARY_SYSTEM_PROMPT = """
Write one short status summary for a marker-checker approval request.
Be concise, factual, and easy to scan.
Do not invent data.
Use plain text only. Do not use Markdown, bullet points, or any special formatting.
""".strip()

REQUEST_HISTORY_SUMMARY_SYSTEM_PROMPT = """
Write one short timeline summary for a marker-checker approval request.
Summarize the current situation from the event history.
Be concise and factual.
Do not invent data.
Use plain text only. Do not use Markdown, bullet points, or any special formatting.
""".strip()

REQUEST_ACTION_RESULT_SYSTEM_PROMPT = """
Write one short user-facing result message for a marker-checker approval action.
Be concise, factual, and clear about the new request state.
Do not invent data.
Use plain text only. Do not use Markdown, bullet points, or any special formatting.
""".strip()

INTENT_CLASSIFY_SYSTEM_PROMPT = """
Classify a user message for a marker-checker approval workflow. Return JSON only.
Keys: operation, request_id, target_name, note, text, target_label, change_from_summary, change_to_summary, approver_handle, guidance_message.

Operations:
- new_request: submit a new approval request (describes a change that needs someone's approval, in any wording or language)
- lookup: check status of a request by its system ID (e.g. REQ-123)
- search: find requests by target/object name when no system request ID is given
- history: view timeline/history of an existing request
- cancel: cancel an existing request
- needinfo: ask for more information about a request
- resubmit: resubmit or update an existing request with new text
- my_pending: list the user's own submitted/active/pending requests
- pending_approvals: list requests waiting for the user to approve
- confirm: confirm a pending draft submission
- unknown: cannot determine intent

Rules:
- request_id: system-assigned ID (e.g. REQ-123, REQ-ABC-456), empty string if none
- target_name: object name for search operation only (e.g. api-gateway, nginx-config), empty string otherwise
- note: any reason or comment the user mentioned, empty string if none
- text: for resubmit only, the new text after the request_id, empty string otherwise
- For new_request, also extract:
  - target_label: the object/system being changed (e.g. api-gateway, feature-X, dashboard)
  - change_from_summary: the current state or old value (infer if clear, e.g. "enabled", "30s", "v1.0")
  - change_to_summary: the desired state or new value (infer if clear, e.g. "disabled", "60s", "v2.0")
  - approver_handle: reviewer with @ prefix (e.g. @john, @ops), empty string if not mentioned
  - guidance_message: short prompt if any field is missing or unclear, empty string if all fields are clear
- All five extraction fields must be empty strings for non-new_request operations.

Examples:
- "list my requests" → {"operation":"my_pending","request_id":"","target_name":"","note":"","text":"","target_label":"","change_from_summary":"","change_to_summary":"","approver_handle":"","guidance_message":""}
- "list các request của tôi" → {"operation":"my_pending","request_id":"","target_name":"","note":"","text":"","target_label":"","change_from_summary":"","change_to_summary":"","approver_handle":"","guidance_message":""}
- "check api-gateway" → {"operation":"search","request_id":"","target_name":"api-gateway","note":"","text":"","target_label":"","change_from_summary":"","change_to_summary":"","approver_handle":"","guidance_message":""}
- "cancel REQ-456 no longer needed" → {"operation":"cancel","request_id":"REQ-456","target_name":"","note":"no longer needed","text":"","target_label":"","change_from_summary":"","change_to_summary":"","approver_handle":"","guidance_message":""}
- "hủy REQ-789 không cần nữa" → {"operation":"cancel","request_id":"REQ-789","target_name":"","note":"không cần nữa","text":"","target_label":"","change_from_summary":"","change_to_summary":"","approver_handle":"","guidance_message":""}
- "tắt feature-X, nhờ @john duyệt" → {"operation":"new_request","request_id":"","target_name":"","note":"","text":"","target_label":"feature-X","change_from_summary":"enabled","change_to_summary":"disabled","approver_handle":"@john","guidance_message":""}
- "change timeout from 30s to 60s for nginx-config, @ops should review" → {"operation":"new_request","request_id":"","target_name":"","note":"","text":"","target_label":"nginx-config","change_from_summary":"30s","change_to_summary":"60s","approver_handle":"@ops","guidance_message":""}
- "deploy v2.1 to prod" → {"operation":"new_request","request_id":"","target_name":"","note":"","text":"","target_label":"prod","change_from_summary":"current version","change_to_summary":"v2.1","approver_handle":"","guidance_message":"Who should approve this deployment?"}
- "ok confirm" → {"operation":"confirm","request_id":"","target_name":"","note":"","text":"","target_label":"","change_from_summary":"","change_to_summary":"","approver_handle":"","guidance_message":""}
""".strip()


def build_request_parse_user_prompt(message: str) -> str:
    return (
        "Extract the approval request fields from this message.\n"
        "The user may describe the request in any natural language.\n"
        "Examples:\n"
        "- 'for nginx-config, change from 30s to 60s, ask @ops to approve'\n"
        "- 'enable dark mode on dashboard, @designer should review'\n"
        "- 'I need @john to approve deploying v2.1 to prod'\n"
        "- 'tắt tính năng beta trên api-gateway, nhờ @manager duyệt giúp'\n"
        "If a value is unclear or not mentioned, leave it as an empty string.\n"
        f"Message: {message}"
    )


def build_clarification_user_prompt(
    *,
    original_message: str,
    missing_fields: list[str],
    validation_errors: list[str],
) -> str:
    return (
        f"Original message: {original_message}\n"
        f"Missing fields: {', '.join(missing_fields) if missing_fields else 'none'}\n"
        f"Validation errors: {'; '.join(validation_errors) if validation_errors else 'none'}\n"
        "Write one short message asking only for the missing or invalid information."
    )


def build_confirmation_user_prompt(*, parsed_request_summary: str) -> str:
    return (
        "Rewrite this request summary into one short user-facing confirmation message.\n"
        f"Summary:\n{parsed_request_summary}"
    )


def build_status_summary_user_prompt(*, request_summary: str) -> str:
    return (
        "Rewrite this request status into one short user-facing summary.\n"
        f"Status:\n{request_summary}"
    )


def build_history_summary_user_prompt(*, request_history: str) -> str:
    return (
        "Rewrite this request event history into one short user-facing summary.\n"
        f"History:\n{request_history}"
    )


def build_action_result_user_prompt(*, action_result: str) -> str:
    return (
        "Rewrite this action result into one short user-facing message.\n"
        f"Action result:\n{action_result}"
    )


def build_intent_classify_user_prompt(message: str) -> str:
    return f"Classify this message:\nMessage: {message}"
