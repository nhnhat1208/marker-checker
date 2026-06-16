"""
Generates contracts/asyncapi.yaml from the WsContract declared in agent.contracts.ws.

Usage:
    uv --project agent run python agent/scripts/gen_asyncapi.py
    make contracts   (runs this then gen-contracts.mjs)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import yaml

# agent/scripts/ -> agent/ -> project root
ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "contracts" / "asyncapi.yaml"


def _clean(obj: Any) -> Any:
    """
    Recursively clean a Pydantic JSON Schema value:
    - Strip JSON Schema `title` annotations (string scalars only — field names
      inside `properties` dicts are never touched).
    - Rewrite `$ref: '#/$defs/X'` → `$ref: '#/components/schemas/X'`.
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    if isinstance(obj, list):
        return [_clean(v) for v in obj]
    out: dict[str, Any] = {}
    for k, v in obj.items():
        if k == "title" and isinstance(v, str):
            continue  # JSON Schema annotation, not a field name
        if k == "$ref" and isinstance(v, str):
            out[k] = v.replace("#/$defs/", "#/components/schemas/")
        elif k == "properties" and isinstance(v, dict):
            out[k] = {field: _clean(schema) for field, schema in v.items()}
        else:
            out[k] = _clean(v)
    return out


def _collect_schemas(contract: Any) -> dict[str, Any]:
    """Extract JSON schemas for all models declared in the contract."""
    schemas: dict[str, Any] = {}
    all_models = (*contract.client_messages, *contract.server_messages)
    for cls in all_models:
        raw: dict[str, Any] = cls.model_json_schema()
        # Pydantic flattens all nested types into a top-level $defs dict.
        for def_name, def_schema in raw.pop("$defs", {}).items():
            if def_name not in schemas:
                schemas[def_name] = _clean(def_schema)
        schemas[cls.__name__] = _clean(raw)
    return schemas


def _component_name(cls: type) -> str:
    """WsTextMessage → TextMessage"""
    return cls.__name__.removeprefix("Ws")


def _channel_key(cls: type) -> str:
    """WsTextMessage → textMessage"""
    name = _component_name(cls)
    return name[0].lower() + name[1:]


def _ref(path: str) -> dict[str, str]:
    return {"$ref": path}


def _build_asyncapi(contract: Any, schemas: dict[str, Any]) -> dict[str, Any]:
    channel_messages = {
        _channel_key(cls): _ref(f"#/components/messages/{_component_name(cls)}")
        for cls in (*contract.client_messages, *contract.server_messages)
    }
    component_messages = {
        _component_name(cls): {
            "summary": (cls.__doc__ or "").strip().split("\n")[0],
            "payload": _ref(f"#/components/schemas/{cls.__name__}"),
        }
        for cls in (*contract.client_messages, *contract.server_messages)
    }

    return {
        "asyncapi": "3.0.0",
        "info": {
            "title": "Marker Checker Agent — WebSocket API",
            "version": "1.0.0",
            "description": (
                "Real-time WebSocket API for the Marker Checker chat interface.\n\n"
                "The client connects to `/ws/chat` and exchanges discriminated-union "
                "messages identified by the `type` field.\n\n"
                "**Client → Server:** text chat, structured request form, or "
                "confirm/discard action.\n"
                "**Server → Client:** typing indicator, completed response, or error.\n"
            ),
        },
        "channels": {
            "chat": {
                "address": contract.channel_address,
                "description": contract.channel_description,
                "messages": channel_messages,
            }
        },
        "operations": {
            "sendMessage": {
                "action": "send",
                "channel": _ref("#/channels/chat"),
                "summary": "Send a message or action to the agent.",
                "messages": [
                    _ref(f"#/channels/chat/messages/{_channel_key(cls)}")
                    for cls in contract.client_messages
                ],
            },
            "receiveMessage": {
                "action": "receive",
                "channel": _ref("#/channels/chat"),
                "summary": "Receive a response or status update from the agent.",
                "messages": [
                    _ref(f"#/channels/chat/messages/{_channel_key(cls)}")
                    for cls in contract.server_messages
                ],
            },
        },
        "components": {
            "messages": component_messages,
            "schemas": schemas,
        },
    }


# ── YAML serialization ────────────────────────────────────────────────────────

class _Dumper(yaml.Dumper):
    pass


def _str_representer(dumper: yaml.Dumper, data: str) -> yaml.Node:
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


_Dumper.add_representer(str, _str_representer)
_Dumper.ignore_aliases = lambda *_: True  # type: ignore[method-assign]


def main() -> None:
    from agent.contracts.ws import WS_CONTRACT

    schemas = _collect_schemas(WS_CONTRACT)
    spec = _build_asyncapi(WS_CONTRACT, schemas)

    header = (
        "# This file is auto-generated from agent/src/agent/contracts/ws.py\n"
        "# Do not edit by hand — run: make contracts\n\n"
    )
    body = yaml.dump(
        spec,
        Dumper=_Dumper,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=100,
    )
    OUTPUT.write_text(header + body, encoding="utf-8")
    sys.stdout.write(f"Wrote {OUTPUT.relative_to(ROOT)}\n")


if __name__ == "__main__":
    main()
