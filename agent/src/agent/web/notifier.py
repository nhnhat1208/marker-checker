from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass
from typing import TYPE_CHECKING

from agent.web.ws_messages import (
    build_request_ui_response,
    done_payload,
    send_ws_message,
)

if TYPE_CHECKING:
    from starlette.websockets import WebSocket

    from agent.domain.models import RequestSummary

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class _SocketRegistration:
    websocket: WebSocket
    loop: asyncio.AbstractEventLoop


class WebNotificationHub:
    def __init__(self) -> None:
        self._connections: dict[str, set[_SocketRegistration]] = {}
        self._lock = threading.Lock()

    def register(
        self,
        *,
        user_email: str,
        websocket: WebSocket,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        email = user_email.strip().casefold()
        if not email:
            return
        registration = _SocketRegistration(websocket=websocket, loop=loop)
        with self._lock:
            self._connections.setdefault(email, set()).add(registration)

    def unregister(self, *, user_email: str, websocket: WebSocket) -> None:
        email = user_email.strip().casefold()
        if not email:
            return
        with self._lock:
            registrations = self._connections.get(email)
            if not registrations:
                return
            registrations = {item for item in registrations if item.websocket is not websocket}
            if registrations:
                self._connections[email] = registrations
            else:
                self._connections.pop(email, None)

    def notify_approver(self, payload: RequestSummary, impact_note: str | None = None) -> None:
        request_id = str(payload.get("request_id", "")).strip()
        approver_handle = str(payload.get("approver_handle", "")).strip().casefold()
        if not approver_handle:
            return
        response = {
            "status": payload.get("review_status", "submitted"),
            "message": f"Request {request_id} is waiting for your approval.",
            "request": payload,
            "ui_response": build_request_ui_response(
                payload,
                title=f"Approval needed · {request_id}" if request_id else "Approval needed",
                body=impact_note or "A new request has been routed to you for review.",
            ).model_dump(mode="json", exclude_none=True),
        }
        self._broadcast(approver_handle, response)

    def notify_requester(self, user_email: str, message: str) -> None:
        email = user_email.strip().casefold()
        if not email:
            return
        self._broadcast(email, {"status": "ok", "message": message})

    def _broadcast(self, user_email: str, response: object) -> None:
        with self._lock:
            registrations = list(self._connections.get(user_email, set()))
        if not registrations:
            return

        payload = done_payload(response)
        for registration in registrations:
            future = asyncio.run_coroutine_threadsafe(
                send_ws_message(registration.websocket, payload),
                registration.loop,
            )
            future.add_done_callback(
                lambda task, email=user_email: LOGGER.debug(
                    "web notification send failed email=%s error=%s",
                    email,
                    task.exception(),
                ) if task.exception() else None
            )


WEB_NOTIFICATION_HUB = WebNotificationHub()
