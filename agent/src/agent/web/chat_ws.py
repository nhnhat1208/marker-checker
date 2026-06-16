from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from agent.contracts.ws import (
    WsActionMessage,
    WsChatHandlerBase,
    WsErrorMessage,
    WsStructuredMessage,
    WsTextMessage,
    WsTypingMessage,
    parse_ws_client_message,
)
from agent.domain.enums import Operation
from agent.domain.models import ActorContext, MessageSource, WorkflowAction
from agent.web.notifier import WEB_NOTIFICATION_HUB
from agent.web.session import get_current_user
from agent.web.ws_messages import done_payload, send_ws_message

if TYPE_CHECKING:
    from agent.config import WebConfig
    from agent.request_coordinator import RequestCoordinator

LOGGER = logging.getLogger(__name__)


class ChatWsHandler(WsChatHandlerBase):
    """Concrete WS handler — one instance per authenticated connection."""

    def __init__(
        self,
        websocket: WebSocket,
        orchestrator: RequestCoordinator,
        actor: ActorContext,
        source: MessageSource,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._ws = websocket
        self._orchestrator = orchestrator
        self._actor = actor
        self._source = source
        self._loop = loop

    async def on_text_message(self, msg: WsTextMessage) -> None:
        text = msg.text.strip()
        if not text:
            return
        await send_ws_message(self._ws, WsTypingMessage(type="typing"))
        response = await self._loop.run_in_executor(
            None,
            lambda t=text: self._orchestrator.handle_requester_message(
                text=t, requester=self._actor, source=self._source
            ),
        )
        await send_ws_message(self._ws, done_payload(response))

    async def on_structured_message(self, msg: WsStructuredMessage) -> None:
        payload = msg.draft.model_dump(mode="json")
        await send_ws_message(self._ws, WsTypingMessage(type="typing"))
        response = await self._loop.run_in_executor(
            None,
            lambda p=payload: self._orchestrator.handle_web_structured_request(
                payload=p, requester=self._actor, source=self._source
            ),
        )
        await send_ws_message(self._ws, done_payload(response))

    async def on_action_message(self, msg: WsActionMessage) -> None:
        await send_ws_message(self._ws, WsTypingMessage(type="typing"))
        if msg.op in {"confirm", "discard"}:
            response = await self._loop.run_in_executor(
                None,
                lambda t=msg.op: self._orchestrator.handle_requester_message(
                    text=t, requester=self._actor, source=self._source
                ),
            )
        else:
            operation = {
                "approve": Operation.APPROVE,
                "reject": Operation.REJECT,
                "needinfo": Operation.NEEDINFO,
            }[msg.op]
            response = await self._loop.run_in_executor(
                None,
                lambda: self._orchestrator.handle_approver_action(
                    actor=self._actor,
                    action=WorkflowAction(
                        action=operation,
                        request_id=(msg.request_id or "").strip(),
                        note=(msg.note or "").strip(),
                    ),
                    source=self._source,
                ),
            )
        await send_ws_message(self._ws, done_payload(response))


def make_chat_ws_handler(
    config: WebConfig,
    orchestrator: RequestCoordinator,
):
    async def chat_ws(websocket: WebSocket) -> None:
        user = get_current_user(dict(websocket.cookies), config.session_secret)
        if user is None:
            await websocket.close(code=4001)
            return

        await websocket.accept()
        user_email = user.email.strip().casefold()
        actor = ActorContext(handle=user_email, name=user.name)
        loop = asyncio.get_running_loop()
        source = MessageSource(source_channel="web", channel_id=user_email, thread_id=user_email)
        WEB_NOTIFICATION_HUB.register(user_email=user_email, websocket=websocket, loop=loop)

        handler = ChatWsHandler(
            websocket=websocket,
            orchestrator=orchestrator,
            actor=actor,
            source=source,
            loop=loop,
        )

        try:
            while True:
                raw = await websocket.receive_text()
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    continue

                try:
                    message = parse_ws_client_message(data)
                except ValidationError:
                    await send_ws_message(
                        websocket,
                        WsErrorMessage(type="error", message="Invalid chat payload."),
                    )
                    continue

                await handler.dispatch(message)

        except WebSocketDisconnect:
            pass
        except Exception as exc:
            LOGGER.warning("chat_ws: unexpected error user=%s error=%s", user.email, exc)
            if websocket.client_state == WebSocketState.CONNECTED:
                await send_ws_message(websocket, WsErrorMessage(type="error", message="Internal error"))
        finally:
            WEB_NOTIFICATION_HUB.unregister(user_email=user_email, websocket=websocket)

    return chat_ws
