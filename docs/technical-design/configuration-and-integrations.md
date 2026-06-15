# Configuration And Integrations

## Configuration Pattern

| File | Purpose | Committed |
| --- | --- | --- |
| `runtime.yaml` | Local app config (secrets + settings) | No — gitignored |
| `runtime.example.yaml` | Template for `runtime.yaml` | Yes |
| `deploy.env` | Env vars for AgentBase deployment | No — gitignored |
| `deploy.example.env` | Template for `deploy.env` | Yes |
| `.greennode.json` | AgentBase IAM credentials | No — gitignored |
| `.greennode.example.json` | Template for `.greennode.json` | Yes |

The application loads YAML first, then applies environment variable overrides. Env vars set to empty strings are ignored (`env_ignore_empty=True`) — this prevents the platform from crashing startup when it injects blank env vars for removed keys during rolling deploys.

## Config Areas

### App

- app name, log level, request ID prefix

### Workflow

- require confirmation before submit
- require rejection reason
- exact lookup behavior

### Telegram

- `enabled` — disable adapter entirely
- `polling_enabled` — disable polling (set to `false` for webhook mode)
- `bot_token`

### Google Sheets

- `enabled`
- `spreadsheet_id`
- `service_account_file` or `service_account_json_base64` (mutually exclusive)
- worksheet names, auto-create flag

### AI

- `enabled` — the workflow works without AI
- `model`, `base_url`, `api_key`
- `max_tokens`, `timeout_seconds`, `temperature`, `top_p`, `presence_penalty`

## Integrations

### Telegram Integration

Request intake, approval actions, status and history lookup. Uses python-telegram-bot v21+ with long polling. During rolling deploys, a 409 Conflict is handled with automatic retry (up to 3 minutes) until the previous container is terminated.

### Google Sheets Integration

Persists requests, audit events, and conversation links across three worksheets. The store caches worksheet values for 15 seconds and invalidates on every write. One replica is the recommended configuration — Sheets is not suited for high concurrent write volume.

### LLM Integration

Optional. Used for request parsing, clarification wording, and status summaries. The workflow falls back to rule-based parsing if AI is disabled or unavailable. Uses `httpx.Client` with a persistent connection pool.

## Container and Deployment

Built with `uv sync --frozen --no-dev` for reproducible installs. Dependencies install in a separate layer — rebuilds only re-install when `pyproject.toml` or `uv.lock` change. `uv.lock` must not be in `.dockerignore`.

Deploy target: GreenNode AgentBase Runtime (Custom Agent), `linux/amd64`. The runtime auto-injects `GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`, `GREENNODE_AGENT_IDENTITY`, `GREENNODE_ENDPOINT_URL` — do not set these in `deploy.env`.

## Secret Handling

Never commit:

- `TELEGRAM_BOT_TOKEN`
- `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` (or service account file)
- `AI_API_KEY`
- `GREENNODE_CLIENT_ID` / `GREENNODE_CLIENT_SECRET`

For local development: keep secrets in `runtime.yaml`.
For deployment: keep secrets in `deploy.env`, passed via `--env-file deploy.env`.

## Integration Rule

External integrations stay behind interfaces (`WorkflowStore`, `RequestInputAssistant`). This keeps workflow logic independent from vendor SDKs and makes storage replaceable.
