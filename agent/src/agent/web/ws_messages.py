from __future__ import annotations

import json
from contextlib import suppress
from typing import TYPE_CHECKING

from pydantic import ValidationError

from agent.contracts.ws import (
    StructuredRequestPayload,
    UiRequestSummary,
    UiResponse,
    WsDoneMessage,
    WsServerMessage,
    dump_ws_server_message,
)

if TYPE_CHECKING:
    from starlette.websockets import WebSocket


async def send_ws_message(websocket: WebSocket, payload: WsServerMessage) -> None:
    with suppress(Exception):
        await websocket.send_text(json.dumps(dump_ws_server_message(payload), default=str))


def done_payload(response: object) -> WsDoneMessage:
    serialized = _serialize(response)
    ui_response = extract_ui_response(serialized)
    response_payload = serialized if isinstance(serialized, dict) else {"value": serialized}
    return WsDoneMessage(type="done", response=response_payload, ui_response=ui_response)


def build_request_ui_response(
    request: dict[str, object],
    *,
    title: str | None = None,
    body: str | None = None,
    kind: str = "request_status",
) -> UiResponse:
    return UiResponse(
        kind=kind,
        title=title,
        body=body,
        status=str(request.get("review_status", "")),
        request=to_ui_request_summary(request),
    )


def extract_ui_response(response: object) -> UiResponse | None:
    if not isinstance(response, dict):
        return None
    candidate = response.get("ui_response")
    if isinstance(candidate, dict):
        coerced = _coerce_ui_response(candidate)
        if coerced is not None:
            return coerced
    request = response.get("request")
    if isinstance(request, dict):
        message = str(response.get("summary_message") or response.get("message") or "").strip()
        return UiResponse(
            kind="request_status",
            status=str(request.get("review_status", response.get("status", ""))),
            body=message or None,
            request=to_ui_request_summary(request),
        )
    requests = response.get("requests")
    if isinstance(requests, list) and all(isinstance(item, dict) for item in requests):
        message = str(response.get("summary_message") or response.get("message") or "").strip()
        return UiResponse(
            kind="request_list",
            requests=[to_ui_request_summary(item) for item in requests],
            status=str(response.get("status", "")),
            body=message or None,
        )
    return None


def to_ui_request_summary(request: dict[str, object]) -> UiRequestSummary:
    structured_payload = request.get("structured_payload")
    payload = None
    if isinstance(structured_payload, dict):
        try:
            payload = StructuredRequestPayload.model_validate(structured_payload)
        except ValidationError:
            payload = None

    return UiRequestSummary(
        request_id=str(request.get("request_id", "Request")),
        requester_handle=str(request.get("requester_handle", "")),
        approver_handle=str(request.get("approver_handle", "")),
        target_label=str(request.get("target_label", "")),
        change_from_summary=str(request.get("change_from_summary", "")),
        change_to_summary=str(request.get("change_to_summary", "")),
        review_status=str(request.get("review_status", "")),
        request_text=str(request.get("request_text", "")),
        structured_payload=payload,
    )


def _serialize(response: object) -> object:
    return json.loads(json.dumps(response, default=str))


def _coerce_ui_response(candidate: dict[str, object]) -> UiResponse | None:
    request = candidate.get("request")
    requests = candidate.get("requests")

    payload: dict[str, object] = {
        "kind": str(candidate.get("kind", "")),
    }
    if isinstance(candidate.get("title"), str):
        payload["title"] = candidate["title"]
    if isinstance(candidate.get("body"), str):
        payload["body"] = candidate["body"]
    if isinstance(candidate.get("status"), str):
        payload["status"] = candidate["status"]
    if isinstance(request, dict):
        payload["request"] = to_ui_request_summary(request)
    if isinstance(requests, list) and all(isinstance(item, dict) for item in requests):
        payload["requests"] = [to_ui_request_summary(item) for item in requests]

    try:
        return UiResponse.model_validate(payload)
    except ValidationError:
        return None
