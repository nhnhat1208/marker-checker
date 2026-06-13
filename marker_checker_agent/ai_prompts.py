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
""".strip()

REQUEST_CONFIRMATION_SYSTEM_PROMPT = """
Write one short confirmation message for a marker-checker approval workflow.
Be concise and easy to verify.
End by telling the user to reply with /confirm.
""".strip()

REQUEST_STATUS_SUMMARY_SYSTEM_PROMPT = """
Write one short status summary for a marker-checker approval request.
Be concise, factual, and easy to scan.
Do not invent data.
""".strip()

REQUEST_HISTORY_SUMMARY_SYSTEM_PROMPT = """
Write one short timeline summary for a marker-checker approval request.
Summarize the current situation from the event history.
Be concise and factual.
Do not invent data.
""".strip()

REQUEST_ACTION_RESULT_SYSTEM_PROMPT = """
Write one short user-facing result message for a marker-checker approval action.
Be concise, factual, and clear about the new request state.
Do not invent data.
""".strip()


def build_request_parse_user_prompt(message: str) -> str:
    return (
        "Parse this approval request.\n"
        "Example: for sample-object, change from disabled to enabled, ask @checker to approve.\n"
        "If from/to is unclear, leave it blank.\n"
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
