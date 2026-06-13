# Configuration And Integrations

## Configuration Goal

Keep configuration small, explicit, and easy to move between local development and AgentBase deployment.

Use:

- one YAML file as the primary configuration source
- optional runtime environment variables only for deploy-specific overrides

## Recommended Files

- `runtime.example.yaml`
- local `runtime.yaml`

Later only:

- `ai-review.yaml`
- additional channel integration files

## Core Config Areas

### Application Runtime

- app name
- environment name
- log level
- primary channel
- persistence backend
- request ID prefix

### Workflow Rules

- requester confirmation required or not
- rejection reason required or not
- lookup strictness

### Telegram Integration

- enabled flag
- polling enabled flag
- bot token
- approver notification prefix

### Google Sheets Integration

- enabled flag
- spreadsheet ID
- worksheet names
- auto-create worksheets flag
- credential source

## Optional Runtime Overrides

Keep environment variables narrow. Use them only when deploy tooling should override local YAML.

Recommended optional variables for this release:

- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_SERVICE_ACCOUNT_FILE`
- `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`

## Secret Handling

Keep these out of committed YAML:

- Telegram bot token
- Google service-account JSON
- any later LLM API keys

Recommended credential pattern:

- local development may use `service_account_file` in `runtime.yaml`
- deployed runtime may use `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` if the platform injects secrets as environment variables

Non-secret values such as spreadsheet ID, request ID prefix, enabled flags, and worksheet names should stay in `runtime.yaml`.

## Integration Pattern

External integrations should follow a small ports-and-adapters structure.

Recommended boundary:

1. workflow core
2. small integration interfaces
3. provider-specific implementations

For the first release, that means:

- `TelegramAdapter` for channel behavior
- `WorkflowStore` for persistence behavior

Later only:

- `DiffSourceAdapter`
- `LLMProviderAdapter`
- `MCPToolAdapter` if truly needed

## Integration Rules

- workflow services must not depend directly on vendor SDK types
- provider-specific auth and payload mapping stay inside adapters
- state must be persisted before outbound notifications are treated as complete
- request and audit logic must not know Google Sheets row details

## Google Sheets Notes

Google Sheets is the chosen first backend because the goal is to avoid deploying a separate database.

Operational rules:

- use one spreadsheet as the shared source of truth
- use one worksheet per logical record set
- share the spreadsheet with the service-account email
- keep one runtime replica first to avoid unnecessary write contention

For locked release decisions, see [Scope And Channel Decision](./scope-and-channel-decision.md).
