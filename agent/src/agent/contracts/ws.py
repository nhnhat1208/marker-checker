from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Literal, assert_never, cast

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter

if TYPE_CHECKING:
    from agent.domain.models import CodeFormat, RequestMode


class StructuredCodeSection(BaseModel):
    """A code block with format metadata."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    format: CodeFormat
    value: str


class StructuredRequestPayload(BaseModel):
    """Full structured change request payload."""

    model_config = ConfigDict(extra="forbid")

    mode: RequestMode
    request_format: CodeFormat
    request: str
    approver: str
    before: StructuredCodeSection
    after: StructuredCodeSection


class UiRequestSummary(BaseModel):
    """Summary of a single change request for UI display."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    requester_handle: str
    approver_handle: str
    target_label: str
    change_from_summary: str
    change_to_summary: str
    review_status: str
    request_text: str
    structured_payload: StructuredRequestPayload | None
    impact_note: str | None = None


class UiDraftSummary(BaseModel):
    """Summary of a pending draft awaiting confirm/discard."""

    model_config = ConfigDict(extra="forbid")

    requester_handle: str
    approver_handle: str
    target_label: str
    change_from_summary: str
    change_to_summary: str
    parser: str


class UiResponse(BaseModel):
    """Structured UI response envelope returned inside a done message."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    title: str | None = None
    body: str | None = None
    status: str | None = None
    request: UiRequestSummary | None = None
    requests: list[UiRequestSummary] | None = None
    draft: UiDraftSummary | None = None
    impact_note: str | None = None
    missing_fields: list[str] | None = None
    guidance_message: str | None = None


# ── Client → Server ───────────────────────────────────────────────────────────

class WsTextMessage(BaseModel):
    """Free-text chat message from the user."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["message"]
    text: str


class WsStructuredMessage(BaseModel):
    """Structured request form submitted by the user."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["structured_message"]
    draft: StructuredRequestPayload


class WsActionMessage(BaseModel):
    """User performs a structured chat action."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["action"]
    op: Literal["confirm", "discard", "approve", "reject", "needinfo"]
    request_id: str | None = None
    note: str | None = None


# ── Server → Client ───────────────────────────────────────────────────────────

class WsTypingMessage(BaseModel):
    """Agent is processing — show typing indicator."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["typing"]


class WsDoneMessage(BaseModel):
    """Agent has finished processing and returns a response."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["done"]
    response: dict[str, Any]
    ui_response: UiResponse | None = None


class WsErrorMessage(BaseModel):
    """An error occurred during processing."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["error"]
    message: str


# ── Discriminated union helpers ───────────────────────────────────────────────

WsClientMessage = Annotated[
    WsTextMessage | WsStructuredMessage | WsActionMessage,
    Field(discriminator="type"),
]

WsServerMessage = Annotated[
    WsTypingMessage | WsDoneMessage | WsErrorMessage,
    Field(discriminator="type"),
]

_WS_CLIENT_ADAPTER: TypeAdapter[WsClientMessage] = TypeAdapter(WsClientMessage)
_WS_SERVER_ADAPTER: TypeAdapter[WsServerMessage] = TypeAdapter(WsServerMessage)


def parse_ws_client_message(payload: object) -> WsTextMessage | WsStructuredMessage | WsActionMessage:
    return _WS_CLIENT_ADAPTER.validate_python(payload)


def dump_ws_server_message(payload: WsServerMessage) -> dict[str, Any]:
    dumped = _WS_SERVER_ADAPTER.dump_python(payload, mode="json", exclude_none=True)
    return cast("dict[str, Any]", dumped)


# ── Contract declaration ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class WsContract:
    """Declares the full WS contract: which models flow each direction."""

    client_messages: tuple[type[BaseModel], ...]
    server_messages: tuple[type[BaseModel], ...]
    channel_address: str
    channel_description: str


WS_CONTRACT = WsContract(
    client_messages=(WsTextMessage, WsStructuredMessage, WsActionMessage),
    server_messages=(WsTypingMessage, WsDoneMessage, WsErrorMessage),
    channel_address="/ws/chat",
    channel_description="Single bidirectional chat channel per authenticated user session.",
)


# ── Handler interface ─────────────────────────────────────────────────────────

def _handler_method_name(cls: type) -> str:
    """WsTextMessage → on_text_message, WsStructuredMessage → on_structured_message."""
    name = cls.__name__.removeprefix("Ws").removesuffix("Message")
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", name).lower()
    return f"on_{snake}_message"


class WsChatHandlerBase(ABC):
    """
    Interface for the WebSocket chat handler.

    Declare one abstract method per client message type in WS_CONTRACT.
    Python raises TypeError at instantiation if any method is not implemented,
    making coverage gaps impossible to miss at server startup or in tests.
    """

    @abstractmethod
    async def on_text_message(self, msg: WsTextMessage) -> None: ...

    @abstractmethod
    async def on_structured_message(self, msg: WsStructuredMessage) -> None: ...

    @abstractmethod
    async def on_action_message(self, msg: WsActionMessage) -> None: ...

    async def dispatch(self, msg: WsTextMessage | WsStructuredMessage | WsActionMessage) -> None:
        if isinstance(msg, WsTextMessage):
            await self.on_text_message(msg)
        elif isinstance(msg, WsStructuredMessage):
            await self.on_structured_message(msg)
        elif isinstance(msg, WsActionMessage):
            await self.on_action_message(msg)
        else:
            assert_never(msg)


# Validate at import time: WsChatHandlerBase abstract methods must cover every
# client message type declared in WS_CONTRACT (by naming convention).
_abstract = frozenset(WsChatHandlerBase.__abstractmethods__)
_missing = [
    _handler_method_name(cls)
    for cls in WS_CONTRACT.client_messages
    if _handler_method_name(cls) not in _abstract
]
if _missing:
    raise NotImplementedError(
        "WsChatHandlerBase missing abstract methods for contract messages: "
        + ", ".join(_missing)
    )
