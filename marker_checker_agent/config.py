from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field
from marker_checker_agent.ai_prompts import REQUEST_PARSE_PROMPT_VERSION


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


class AIConfig(BaseModel):
    enabled: bool = False
    prompt_version: str = REQUEST_PARSE_PROMPT_VERSION
    model: str = ""
    base_url: str = "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
    api_key: str = ""
    timeout_seconds: float = 15.0
    max_tokens: int = 800
    temperature: float = 0.0
    top_p: float = 0.95
    presence_penalty: float = 0.0


class RuntimeConfig(BaseModel):
    app: AppConfig = Field(default_factory=AppConfig)
    workflow: WorkflowConfig = Field(default_factory=WorkflowConfig)
    telegram: TelegramConfig = Field(default_factory=TelegramConfig)
    google_sheets: GoogleSheetsConfig = Field(default_factory=GoogleSheetsConfig)
    ai: AIConfig = Field(default_factory=AIConfig)


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
        if not isinstance(data, dict):
            return {}
        return data


def _apply_environment_overrides(config: RuntimeConfig) -> RuntimeConfig:
    def string_override(env_name: str, current_value: str) -> str:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            return current_value
        return raw_value.strip()

    def int_override(env_name: str, current_value: int) -> int:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            return current_value
        try:
            return int(raw_value.strip())
        except ValueError:
            return current_value

    def float_override(env_name: str, current_value: float) -> float:
        raw_value = os.getenv(env_name)
        if raw_value is None:
            return current_value
        try:
            return float(raw_value.strip())
        except ValueError:
            return current_value

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
        "bot_token": string_override("TELEGRAM_BOT_TOKEN", config.telegram.bot_token),
    }

    google_sheets_overrides: dict[str, Any] = {
        "enabled": bool_override(
            "GOOGLE_SHEETS_ENABLED",
            config.google_sheets.enabled,
        ),
        "spreadsheet_id": string_override(
            "GOOGLE_SHEETS_SPREADSHEET_ID",
            config.google_sheets.spreadsheet_id,
        ),
        "service_account_file": string_override(
            "GOOGLE_SERVICE_ACCOUNT_FILE",
            config.google_sheets.service_account_file,
        ),
        "service_account_json_base64": string_override(
            "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64",
            config.google_sheets.service_account_json_base64,
        ),
        "auto_create_worksheets": bool_override(
            "GOOGLE_SHEETS_AUTO_CREATE_WORKSHEETS",
            config.google_sheets.auto_create_worksheets,
        ),
    }

    ai_overrides: dict[str, Any] = {
        "enabled": bool_override("AI_ENABLED", config.ai.enabled),
        "prompt_version": string_override(
            "AI_PROMPT_VERSION",
            config.ai.prompt_version,
        ),
        "model": string_override("AI_MODEL", config.ai.model),
        "base_url": string_override("AI_BASE_URL", config.ai.base_url),
        "api_key": string_override("AI_API_KEY", config.ai.api_key),
        "timeout_seconds": float_override(
            "AI_TIMEOUT_SECONDS",
            config.ai.timeout_seconds,
        ),
        "max_tokens": int_override("AI_MAX_TOKENS", config.ai.max_tokens),
        "temperature": float_override("AI_TEMPERATURE", config.ai.temperature),
        "top_p": float_override("AI_TOP_P", config.ai.top_p),
        "presence_penalty": float_override(
            "AI_PRESENCE_PENALTY",
            config.ai.presence_penalty,
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
        ai={**config.ai.model_dump(), **ai_overrides},
    )


def _validate_runtime_config(config: RuntimeConfig) -> RuntimeConfig:
    errors: list[str] = []

    if config.telegram.enabled and not config.telegram.bot_token.strip():
        errors.append(
            "telegram.bot_token is required when telegram.enabled is true. "
            "Set it in runtime.yaml or TELEGRAM_BOT_TOKEN."
        )

    if config.google_sheets.enabled:
        if not config.google_sheets.spreadsheet_id.strip():
            errors.append(
                "google_sheets.spreadsheet_id is required when "
                "google_sheets.enabled is true."
            )

        has_service_account_file = bool(config.google_sheets.service_account_file.strip())
        has_service_account_base64 = bool(
            config.google_sheets.service_account_json_base64.strip()
        )
        if not has_service_account_file and not has_service_account_base64:
            errors.append(
                "Google Sheets credentials are required when google_sheets.enabled "
                "is true. Set google_sheets.service_account_file, "
                "google_sheets.service_account_json_base64, "
                "GOOGLE_SERVICE_ACCOUNT_FILE, or "
                "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64."
            )

    if config.ai.enabled:
        if not config.ai.model.strip():
            errors.append("ai.model is required when ai.enabled is true.")
        if not config.ai.base_url.strip():
            errors.append("ai.base_url is required when ai.enabled is true.")
        if not config.ai.api_key.strip():
            errors.append("ai.api_key is required when ai.enabled is true.")

    if errors:
        raise ValueError("Invalid runtime configuration:\n- " + "\n- ".join(errors))

    return config


def load_runtime_config(base_dir: Path | None = None) -> RuntimeConfig:
    root = base_dir or Path.cwd()
    runtime_path = root / "runtime.yaml"
    if not runtime_path.exists():
        runtime_path = root / "runtime.example.yaml"
    if not runtime_path.exists():
        raise FileNotFoundError(
            "Missing runtime config. Expected runtime.yaml for local use or "
            "runtime.example.yaml as the packaged baseline config."
        )

    runtime_config = _load_yaml_file(runtime_path)

    config = RuntimeConfig(**runtime_config)
    config = _apply_environment_overrides(config)
    return _validate_runtime_config(config)
