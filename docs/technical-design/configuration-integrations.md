# Configuration, Integrations

## Config Files

| File | Purpose | Committed |
| --- | --- | --- |
| `runtime.yaml` | Non-secret app config (structure + defaults) | Yes |
| `deploy.env` | Secret env vars for AgentBase deployment | No — gitignored |
| `deploy.example.env` | Template for `deploy.env` | Yes |
| `.greennode.json` | AgentBase IAM credentials | No — gitignored |
| `.greennode.example.json` | Template for `.greennode.json` | Yes |

**Config split:** `runtime.yaml` holds all non-secret configuration (polling mode, persistence backend, worksheet names, AI model, timeouts) and is committed to git. `runtime.local.yaml` (gitignored) overrides for local development (e.g. `telegram: mode: polling`). Secrets (`TELEGRAM_BOT_TOKEN`, `POSTGRES_DSN`, `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64`, `AI_API_KEY`, `GOOGLE_SHEETS_SPREADSHEET_ID`) come from environment variables only — never in `runtime.yaml`.

The application loads YAML first, then applies environment variable overrides. Env vars set to empty strings are ignored (`env_ignore_empty=True`) — this prevents the platform from crashing startup when it injects blank env vars for removed keys during rolling deploys.

## Main Settings

### App

- app name, log level, request ID prefix

### Workflow

- require confirmation before submit
- require rejection reason
- exact lookup behavior

### Telegram

- `enabled` — disable adapter entirely
- `mode` — `webhook` (production default) or `polling` (local dev fallback); set via `runtime.local.yaml` or `TELEGRAM_MODE` env var
- `bot_token`
- `webhook_url` — explicit public URL for Telegram's `setWebhook` call (set via `TELEGRAM_WEBHOOK_URL` in `deploy.env`); falls back to `GREENNODE_ENDPOINT_URL + /telegram-webhook` if not set, but note that `GREENNODE_ENDPOINT_URL` is the internal invocation URL and may not be reachable from Telegram's servers

### Persistence

- `backend` — `postgres` (default) or `google_sheets`; overridable via `PERSISTENCE_BACKEND` env var or `runtime.local.yaml`

### Google Sheets

Only used when `persistence.backend: google_sheets`.

- `spreadsheet_id`
- `service_account_file` or `service_account_json_base64` (mutually exclusive)
- worksheet names (`requests`, `audit_events`, `request_conversations`, `chat_registry`, `pending_drafts`, `pending_resubmit`), auto-create flag

### AI

- `enabled` — the workflow works without AI
- `model`, `base_url`, `api_key`
- `max_tokens`, `timeout_seconds`, `temperature`, `top_p`, `presence_penalty`

### Memory

- `memory_id` — Memory store ID from AgentBase console; set via `MEMORY_MEMORY_ID`. When empty, memory is disabled.
- `user_pref_strategy_id` — LTMS ID for extracting user preferences
- `approver_behavior_strategy_id` — LTMS ID for extracting approver behavior patterns

### Web UI

Web UI is enabled automatically when `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are both non-empty. There is no explicit `enabled` flag — presence of credentials drives the feature.

- `GOOGLE_CLIENT_ID` — OAuth 2.0 client ID from Google Cloud Console
- `GOOGLE_CLIENT_SECRET` — OAuth 2.0 client secret
- `GOOGLE_REDIRECT_URI` — optional; derived from the incoming request URL if empty. Set explicitly when using a custom domain or when local/dev routing needs a fixed callback URL.
- `GOOGLE_SESSION_SECRET` — random secret for signing httponly session cookies (itsdangerous, 7-day TTL). Required when web is enabled.

## External Services

### Web UI Integration

Chat-first web interface served from the same container as the Python backend. Uses Google OAuth 2.0 for authentication — any Google account can log in (no allowlist). Session is maintained via an httponly signed cookie (`itsdangerous`, 7-day TTL).

Routes registered when web is enabled:

- `GET /auth/google` → redirect to Google consent screen
- `GET /auth/callback` → exchange code, set session cookie, redirect `/`
- `GET /auth/logout` → clear cookie
- `GET /api/me` → `{ email, name, avatar_url }`
- `WS /ws/chat` → WebSocket chat, piped to `RequestCoordinator`
- `GET /*` → SPA fallback (serves `index.html`)

The React frontend (`frontend/`) is built with Rsbuild (Rspack/Rust) + Tailwind CSS, copied into `/app/static` at image build time via a multi-stage Dockerfile (Node 22 + pnpm 10 → Python 3.11 slim). No separate Node.js process in production — FastAPI serves the static bundle directly.

### Telegram Integration

Request intake, approval actions, status and history lookup. Uses python-telegram-bot v21+. In production (AgentBase Runtime), Telegram pushes updates via webhook to `/telegram-webhook`; the container registers the webhook URL on startup using `TELEGRAM_WEBHOOK_URL` (set in `deploy.env`). `GREENNODE_ENDPOINT_URL` is the internal invocation URL — not publicly routable from Telegram's servers — so `TELEGRAM_WEBHOOK_URL` must point to the public AgentBase endpoint URL (`agentbase-runtime.aiplatform.vngcloud.vn`). `setWebhook` retries up to 5 times with exponential backoff on failure. For local development, long polling is used as a fallback (`TELEGRAM_MODE=polling` via `runtime.local.yaml` or env var). During rolling deploys with polling enabled, a 409 Conflict is handled with automatic retry (up to 3 minutes).

#### Testing Locally

Local Telegram testing flow:

1. create a bot with BotFather using `/newbot`
2. copy the token into `deploy.env` as `TELEGRAM_BOT_TOKEN`
3. set `telegram.mode: polling` in `runtime.local.yaml`
4. run `make run`
5. send `/start` to the bot from each Telegram account involved in the test

Why `/start` matters:

- the app stores a handle-to-`chat_id` mapping in `chat_registry`
- approver notifications can only be sent after that approver has already interacted with the bot once
- if an approver never messaged the bot, the request still exists, but Telegram notification is skipped until the mapping is known

Recommended manual test:

1. requester account sends a new change request
2. requester confirms the generated draft
3. approver account receives the notification and responds with inline buttons or `/approve`, `/reject`, `/needinfo`
4. requester account receives the follow-up result notification

### PostgreSQL (Neon) Integration

Default persistence backend. Uses a thread-safe `ThreadedConnectionPool`. All upserts use `ON CONFLICT DO UPDATE` so concurrent writes are safe. DDL (table creation) runs automatically on startup — no manual schema migration needed. Connection string via `POSTGRES_DSN` in `deploy.env`. Neon free tier has no auto-pause when there is regular traffic.

### Google Sheets Integration

Legacy fallback backend — active only when `persistence.backend: google_sheets`. Persists requests, audit events, conversation links, session state (pending drafts, pending resubmit), and chat registry across six worksheets. The store caches worksheet values for 15 seconds and invalidates on every write. One replica is the recommended configuration — Sheets is not suited for high concurrent write volume.

### LLM Integration

Optional. Used for request parsing, clarification wording, and status summaries. The workflow falls back to rule-based parsing if AI is disabled or unavailable. Uses `httpx.Client` with a persistent connection pool. For new-request processing, `classify_intent` and `assist_request_text` run concurrently via `ThreadPoolExecutor` (speculative execution), reducing effective LLM latency to `max(classify, assist)` instead of sequential.

### Memory Service Integration

Optional. Uses AgentBase Memory Service for user preference recall and approver behavior pattern extraction. Requires a Memory store with two LTMS strategies configured. When disabled, the workflow uses static defaults.

## Deployment

Built with `uv sync --frozen --no-dev` for reproducible installs. Dependencies install in a separate layer — rebuilds only re-install when `pyproject.toml` or `uv.lock` change. `uv.lock` must not be in `.dockerignore`.

Deploy target: GreenNode AgentBase Runtime (Custom Agent), `linux/amd64`. The runtime auto-injects `GREENNODE_CLIENT_ID`, `GREENNODE_CLIENT_SECRET`, `GREENNODE_AGENT_IDENTITY`, `GREENNODE_ENDPOINT_URL` — do not set these in `deploy.env`.

### Deploy Commands

```bash
make deploy
```

After deploy: verify Telegram webhook is registered and `/start` responds.

## Secret Handling

Never commit:

- `TELEGRAM_BOT_TOKEN`
- `POSTGRES_DSN`
- `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` (or service account file) — only needed for `google_sheets` backend
- `AI_API_KEY`
- `GREENNODE_CLIENT_ID` / `GREENNODE_CLIENT_SECRET`

For local development: keep secrets in environment variables or `runtime.local.yaml` (gitignored).
For deployment: keep secrets in `deploy.env` (gitignored), passed via `--env-file deploy.env`.

## Design Rule

External integrations stay behind interfaces (`WorkflowStore`, `RequestInputAssistant`). This keeps workflow logic independent from vendor SDKs and makes storage replaceable.
