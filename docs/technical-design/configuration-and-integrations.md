# Configuration And Integrations

## Configuration Pattern

Use:

- `runtime.yaml` for local config
- `runtime.example.yaml` as the committed template
- `.agentbase/deploy.env` for deploy-time overrides

The application loads YAML first, then applies environment variable overrides.

## Main Config Areas

### App

- app name
- log level
- request ID prefix

### Workflow

- require confirmation
- require rejection reason
- exact lookup behavior

### Telegram Config

- enabled
- polling enabled
- bot token

### Google Sheets Config

- enabled
- spreadsheet ID
- service account file or base64 JSON
- worksheet names

### AI

- enabled
- model
- base URL
- API key
- token and timeout tuning

## Main Integrations

### Telegram

Used for:

- request intake
- approval actions
- status and history lookup

### Google Sheets

Used for:

- requests
- audit events
- request conversation links

### LLM Provider

Optional.

Used for:

- request parsing help
- clarification and summary wording

The workflow still works without AI.

## Container and Deployment

The `Dockerfile` uses `uv` (not pip) for dependency installation:

- `uv sync --frozen --no-dev` pins exact versions from `uv.lock`
- Dependencies are installed in a separate layer before source copy — rebuilds only re-install when `pyproject.toml` or `uv.lock` change
- `PYTHONUNBUFFERED=1` ensures logs flush immediately to container stdout

Deploy target is GreenNode AgentBase Runtime (Custom Agent). The runtime auto-injects `GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`, `GREENNODE_AGENT_IDENTITY`, `GREENNODE_ENDPOINT_URL` — do not set these in the env file.

The `uv.lock` file must not be in `.dockerignore` — it is required for reproducible builds.

## Secret Handling

Do not commit:

- Telegram bot token
- Google service account credentials
- AI API key

Recommended:

- local: keep secrets in `runtime.yaml`
- deploy: keep secrets in `.agentbase/deploy.env`

## Integration Rule

External integrations should stay behind interfaces.

That keeps:

- workflow logic independent from vendor SDKs
- storage replaceable later
- AI optional instead of central to the system
