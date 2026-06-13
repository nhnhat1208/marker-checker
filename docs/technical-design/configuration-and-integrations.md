# Configuration And Integrations

## Configuration Goal

Keep configuration small, explicit, and easy to move between local development and AgentBase deployment.

Use:

- one YAML file as the primary configuration source
- `pydantic-settings` for automatic env var override (no manual override code)

## Recommended Files

- `runtime.yaml` — local working config (not committed)
- `runtime.example.yaml` — committed template, secret-free

## Config Classes

Each class maps to a YAML section and an env prefix. Environment variables at that prefix override YAML values automatically.

| Class | YAML key | Env prefix |
| --- | --- | --- |
| `AppConfig` | `app` | — |
| `WorkflowConfig` | `workflow` | — |
| `TelegramConfig` | `telegram` | `TELEGRAM_` |
| `GoogleSheetsConfig` | `google_sheets` | `GOOGLE_SHEETS_` |
| `AIConfig` | `ai` | `AI_` |

## Core Config Areas

### Application Runtime

```yaml
app:
  name: "marker-checker-agent"
  env: "local"
  log_level: "INFO"
  primary_channel: "telegram"
  request_id_prefix: "REQ"
  persistence_backend: "google_sheets"
```

### Workflow Rules

```yaml
workflow:
  require_confirmation: true
  reject_requires_reason: true
  exact_lookup_only: true
```

### Telegram Integration

```yaml
telegram:
  enabled: true
  polling_enabled: true
  bot_token: ""
```

Env overrides: `TELEGRAM_ENABLED`, `TELEGRAM_POLLING_ENABLED`, `TELEGRAM_BOT_TOKEN`

### Google Sheets Integration

```yaml
google_sheets:
  enabled: true
  spreadsheet_id: ""
  service_account_file: ""
  service_account_json_base64: ""
  auto_create_worksheets: true
  worksheets:
    requests: "requests"
    audit_events: "audit_events"
    request_conversations: "request_conversations"
```

Env overrides:

| Variable | Field |
| --- | --- |
| `GOOGLE_SHEETS_ENABLED` | `enabled` |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | `spreadsheet_id` |
| `GOOGLE_SERVICE_ACCOUNT_FILE` | `service_account_file` |
| `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` | `service_account_json_base64` |
| `GOOGLE_SHEETS_AUTO_CREATE_WORKSHEETS` | `auto_create_worksheets` |

Note: `GOOGLE_SERVICE_ACCOUNT_FILE` and `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` do not follow the `GOOGLE_SHEETS_` prefix because they predate it. Both spellings are accepted via `AliasChoices`.

### AI / LLM Integration

```yaml
ai:
  enabled: false
  model: ""
  base_url: "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
  api_key: ""
  prompt_version: "request-parse-v1"
  max_tokens: 800
  temperature: 0.0
  top_p: 0.95
  timeout_seconds: 15.0
  presence_penalty: 0.0
```

Env overrides:

| Variable | Field |
| --- | --- |
| `AI_ENABLED` | `enabled` |
| `AI_MODEL` | `model` |
| `AI_BASE_URL` | `base_url` |
| `AI_API_KEY` | `api_key` |
| `AI_PROMPT_VERSION` | `prompt_version` |
| `AI_MAX_TOKENS` | `max_tokens` |
| `AI_TEMPERATURE` | `temperature` |
| `AI_TOP_P` | `top_p` |
| `AI_TIMEOUT_SECONDS` | `timeout_seconds` |
| `AI_PRESENCE_PENALTY` | `presence_penalty` |

When `AI_ENABLED=true`, the agent activates:

1. **Intent classification** — classify management operations from freeform text (max 80 tokens)
2. **Request parsing** — extract structured fields when regex pattern fails

## Secret Handling

Keep these out of committed YAML:

- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` / `GOOGLE_SERVICE_ACCOUNT_FILE`
- `AI_API_KEY`

Recommended patterns:

- local dev: use `service_account_file` path in `runtime.yaml`
- deploy: use `.agentbase/deploy.env` with `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`

## Integration Pattern

Follow a ports-and-adapters structure:

1. workflow core (`RequestService`, `AuditService`)
2. integration interfaces (`WorkflowStore`, `RequestInputAssistant`)
3. provider-specific implementations (`GoogleSheetsWorkflowStore`, `OpenAICompatibleInputAssistant`)

## Integration Rules

- workflow services must not depend directly on vendor SDK types
- provider-specific auth and payload mapping stay inside adapters
- state must be persisted before outbound notifications are treated as complete
- request and audit logic must not know Google Sheets row details

## Google Sheets Notes

- use one spreadsheet as the shared source of truth
- use one worksheet per logical record set
- share the spreadsheet with the service-account email
- keep one runtime replica to avoid write contention
- auto-create worksheets is safe for first setup; worksheet names are explicit in YAML

For locked release decisions, see [Scope And Channel Decision](./scope-and-channel-decision.md).
