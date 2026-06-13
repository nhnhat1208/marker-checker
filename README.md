# marker-checker

AgentBase Custom Agent for a simple marker-checker approval workflow.

## What It Does

- requester sends a change request in natural language
- agent parses the message (regex pattern or LLM-assisted) and asks for confirmation
- approver approves, rejects, cancels, or asks for more info
- LLM intent classification routes management commands (lookup, cancel, history, etc.) even without strict syntax
- request state and audit history are stored in Google Sheets
- the same workflow is available from Telegram and `POST /invocations`

## Read More

- full doc map: [docs/README.md](docs/README.md)
- product workflow: [docs/product-spec/workflow-and-lifecycle.md](docs/product-spec/workflow-and-lifecycle.md)
- configuration details: [docs/technical-design/configuration-and-integrations.md](docs/technical-design/configuration-and-integrations.md)
- architecture: [docs/technical-design/architecture.md](docs/technical-design/architecture.md)

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — install once:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Local Setup

```bash
make setup
```

This runs `uv sync` (installs all deps into `.venv`) and creates `runtime.yaml` from the example template if it does not exist yet.

### Google Sheets Setup

1. Create a Google Sheet.
2. Enable `Google Sheets API` (and `Google Drive API` if needed).
3. Create or reuse a service account, share the spreadsheet with its email.
4. Put the spreadsheet ID and credentials in `runtime.yaml`.

Default worksheets created automatically: `requests`, `audit_events`, `request_conversations`.

## Configuration

`runtime.yaml` is the primary local config. `runtime.example.yaml` is the committed template.

Fill at minimum:

- `telegram.bot_token`
- `google_sheets.spreadsheet_id`
- one of `service_account_file` or `service_account_json_base64`

### Optional LLM Input Assistance

When `ai.enabled: true`, the agent uses an LLM for two purposes:

1. **Request parsing** — extract structured fields from free-form text when the regex pattern fails
2. **Intent classification** — route management commands (lookup, cancel, history, etc.) even when phrasing does not match the built-in patterns

```yaml
ai:
  enabled: true
  model: "your-model-id"
  base_url: "https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1"
  api_key: "..."
  prompt_version: "request-parse-v1"
  max_tokens: 800
  temperature: 0.0
  top_p: 0.95
  timeout_seconds: 15
  presence_penalty: 0.0
```

All config values can be overridden at deploy time with environment variables. See [Configuration And Integrations](docs/technical-design/configuration-and-integrations.md) for the full variable list.

## Run Locally

```bash
make run
```

Disable Telegram polling if needed:

```bash
make run-no-telegram
```

## Testing

```bash
make test
```

Validate config only:

```bash
make config-check
```

Check health endpoint:

```bash
make health
```

Send a sample invocation:

```bash
make invoke-sample
```

Real LLM smoke test (requires working AI config):

```bash
make ai-smoke
```

## Telegram Commands

| Command | Description |
|---------|-------------|
| _(plain text)_ | Submit or clarify a request |
| `/confirm` | Confirm a pending draft |
| `/approve REQ-...` | Approve a request |
| `/reject REQ-... reason` | Reject with reason |
| `/needinfo REQ-... note` | Ask requester for more info |
| `/cancel REQ-...` | Cancel a request |
| `/status REQ-...` | Look up request status |
| `/history REQ-...` | Show audit timeline |

## Deploy Preparation

Secrets needed for deployment:

- `.greennode.json` — AgentBase IAM credentials

```json
{
  "client_id": "...",
  "client_secret": "..."
}
```

- `.agentbase/deploy.env` — runtime env overrides (never committed)

Recommended deploy env keys:

```env
TELEGRAM_ENABLED=true
TELEGRAM_POLLING_ENABLED=false
TELEGRAM_BOT_TOKEN=...
GOOGLE_SHEETS_ENABLED=true
GOOGLE_SHEETS_SPREADSHEET_ID=...
GOOGLE_SHEETS_AUTO_CREATE_WORKSHEETS=true
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=...
AI_ENABLED=false
AI_MODEL=...
AI_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
AI_API_KEY=...
AI_PROMPT_VERSION=request-parse-v1
AI_TIMEOUT_SECONDS=30
AI_MAX_TOKENS=250
AI_TEMPERATURE=0.0
AI_TOP_P=0.95
AI_PRESENCE_PENALTY=0.0
```

Local Docker build:

```bash
make docker-build
```

## Deploy To AgentBase

Use the AgentBase skills in Claude Code. Typical prompts:

```text
Use /agentbase-deploy to log in to AgentBase Container Registry for this project.
```

```text
Use /agentbase-deploy to deploy this repo as a Custom Agent.
Use `.agentbase/deploy.env` as the runtime env file.
Use AgentBase managed Container Registry.
Use linux/amd64.
Use flavor `runtime-s2-general-2x4`.
Use 1 min replica and 1 max replica.
```

Redeploy:

```text
Use /agentbase-deploy to redeploy the existing runtime for this repo with `.agentbase/deploy.env`.
```

Verify deployment:

```bash
curl -s -i https://<endpoint-url>/health
```

```bash
curl -s -i -X POST https://<endpoint-url>/invocations \
  -H 'Content-Type: application/json' \
  -d '{"message":"for sample-object, change from disabled to enabled, ask @checker to approve","actor_name":"Requester One","actor_handle":"@requester"}'
```

## Notes

- Workflow state is always rule-based — AI is advisory only, never authoritative.
- When AI is disabled, all routing falls back to regex patterns.
- The agent follows the OpenAI-compatible `/v1/chat/completions` API so any compatible model provider works.
