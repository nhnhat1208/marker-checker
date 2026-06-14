from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import AliasChoices, BaseModel, Field
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict


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


class _EnvFirstSettings(BaseSettings):
    """BaseSettings where env vars take priority over constructor kwargs (YAML values)."""

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return env_settings, init_settings, file_secret_settings


class TelegramConfig(_EnvFirstSettings):
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")

    enabled: bool = True
    polling_enabled: bool = True
    bot_token: str = ""


class GoogleSheetsWorksheetConfig(BaseModel):
    requests: str = "requests"
    audit_events: str = "audit_events"
    request_conversations: str = "request_conversations"


class GoogleSheetsConfig(_EnvFirstSettings):
    model_config = SettingsConfigDict(env_prefix="GOOGLE_SHEETS_", populate_by_name=True)

    enabled: bool = True
    spreadsheet_id: str = ""
    service_account_file: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_SERVICE_ACCOUNT_FILE",
            "GOOGLE_SHEETS_SERVICE_ACCOUNT_FILE",
        ),
    )
    service_account_json_base64: str = Field(
        default="",
        validation_alias=AliasChoices(
            "GOOGLE_SERVICE_ACCOUNT_JSON_BASE64",
            "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON_BASE64",
        ),
    )
    auto_create_worksheets: bool = True
    worksheets: GoogleSheetsWorksheetConfig = Field(default_factory=GoogleSheetsWorksheetConfig)


class AIConfig(_EnvFirstSettings):
    model_config = SettingsConfigDict(env_prefix="AI_")

    enabled: bool = False
    prompt_version: str = "request-parse-v1"
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

    yaml_data = _load_yaml_file(runtime_path)

    config = RuntimeConfig(
        app=AppConfig(**(yaml_data.get("app") or {})),
        workflow=WorkflowConfig(**(yaml_data.get("workflow") or {})),
        telegram=TelegramConfig(**(yaml_data.get("telegram") or {})),
        google_sheets=GoogleSheetsConfig(**(yaml_data.get("google_sheets") or {})),
        ai=AIConfig(**(yaml_data.get("ai") or {})),
    )
    return _validate_runtime_config(config)
