from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    name: str = "marker-checker-agent"
    env: str = "local"
    log_level: str = "INFO"
    primary_channel: str = "telegram"
    request_id_prefix: str = "REQ"
    persistence_backend: str = "google_sheets"


class WorkflowConfig(BaseModel):
    require_confirmation: bool = True
    reject_requires_reason: bool = True
    exact_lookup_only: bool = True


class TelegramConfig(BaseModel):
    enabled: bool = True
    polling_enabled: bool = True
    bot_token: str = ""
    approver_notification_prefix: str = "Approval request"


class GoogleSheetsWorksheetConfig(BaseModel):
    requests: str = "requests"
    audit_events: str = "audit_events"
    request_conversations: str = "request_conversations"


class GoogleSheetsConfig(BaseModel):
    enabled: bool = True
    spreadsheet_id: str = ""
    service_account_file: str = ""
    service_account_json_base64: str = ""
    auto_create_worksheets: bool = True
    worksheets: GoogleSheetsWorksheetConfig = Field(
        default_factory=GoogleSheetsWorksheetConfig
    )


class RuntimeConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    google_sheets: GoogleSheetsConfig = Field(default_factory=GoogleSheetsConfig)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            return {}
        return data


def _apply_environment_overrides(config: RuntimeConfig) -> RuntimeConfig:
    def bool_override(env_name: str, current_value: bool) -> bool:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            return current_value

        normalized = raw_value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
        return current_value

    telegram_overrides = {
        "enabled": bool_override("TELEGRAM_ENABLED", config.telegram.enabled),
        "polling_enabled": bool_override(
            "TELEGRAM_POLLING_ENABLED",
            config.telegram.polling_enabled,
        ),
        "bot_token": os.getenv("TELEGRAM_BOT_TOKEN", config.telegram.bot_token),
    }

    google_sheets_overrides: dict[str, Any] = {
        "enabled": bool_override(
            "GOOGLE_SHEETS_ENABLED",
            config.google_sheets.enabled,
        ),
        "spreadsheet_id": os.getenv(
            "GOOGLE_SHEETS_SPREADSHEET_ID",
            config.google_sheets.spreadsheet_id,
        ),
        "service_account_file": os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_FILE",
            config.google_sheets.service_account_file,
        ),
        "service_account_json_base64": os.getenv(
            "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64",
            config.google_sheets.service_account_json_base64,
        ),
        "auto_create_worksheets": bool_override(
            "GOOGLE_SHEETS_AUTO_CREATE_WORKSHEETS",
            config.google_sheets.auto_create_worksheets,
        ),
    }

    return RuntimeConfig(
        app=config.app.model_dump(),
        workflow=config.workflow.model_dump(),
        telegram={**config.telegram.model_dump(), **telegram_overrides},
        google_sheets={
            **config.google_sheets.model_dump(),
            **google_sheets_overrides,
        },
    )


def load_runtime_config(base_dir: Path | None = None) -> RuntimeConfig:
    root = base_dir or Path.cwd()
    runtime_path = root / "runtime.yaml"
    if not runtime_path.exists():
        runtime_path = root / "runtime.example.yaml"

    runtime_config = _load_yaml_file(runtime_path)

    config = RuntimeConfig(**runtime_config)
    return _apply_environment_overrides(config)
