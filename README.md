# marker-checker

AgentBase Custom Agent for a simple marker-checker approval workflow.

## What It Does

- requester sends a change request
- agent parses the message and asks for confirmation
- approver approves, rejects, cancels, or asks for more info
- request state and audit history are stored in Google Sheets
- the same workflow is available from Telegram and `POST /invocations`

## Read More

- full doc map: [docs/README.md](/Users/lap15852/Documents/Projects/clawathon/marker-checker/docs/README.md)
- product workflow: [docs/product-spec/workflow-and-lifecycle.md](/Users/lap15852/Documents/Projects/clawathon/marker-checker/docs/product-spec/workflow-and-lifecycle.md)
- configuration details: [docs/technical-design/configuration-and-integrations.md](/Users/lap15852/Documents/Projects/clawathon/marker-checker/docs/technical-design/configuration-and-integrations.md)
- architecture: [docs/technical-design/architecture.md](/Users/lap15852/Documents/Projects/clawathon/marker-checker/docs/technical-design/architecture.md)
- delivery and rollout: [docs/delivery-plan/implementation-plan.md](/Users/lap15852/Documents/Projects/clawathon/marker-checker/docs/delivery-plan/implementation-plan.md)

## Configuration

- `runtime.yaml` is the primary local config
- `runtime.example.yaml` is only a template
- app loads `runtime.yaml` first, then falls back to `runtime.example.yaml`
- deploy-time overrides go in `.agentbase/deploy.env`

Create local config:

```bash
cp runtime.example.yaml runtime.yaml
```

Or:

```bash
make setup-config
```

Fill at least:

- `telegram.bot_token`
- `google_sheets.spreadsheet_id`
- one Google credential source

Optional for LLM input assistance:

- `ai.enabled`
- `ai.prompt_version`
- `ai.model`
- `ai.base_url`
- `ai.api_key`
- `ai.max_tokens`
- `ai.temperature`
- `ai.top_p`
- `ai.presence_penalty`

## Local Setup

```bash
make setup
```

### Google Sheets Setup

1. Create a Google Sheet.
2. Enable `Google Sheets API`.
3. Enable `Google Drive API` if your current scopes still require it.
4. Create or reuse a service account.
5. Share the spreadsheet with the service-account email.
6. Put the spreadsheet ID and credentials in `runtime.yaml`.

Default worksheets:

- `requests`
- `audit_events`
- `request_conversations`

## Run Locally

```bash
make run
```

Disable Telegram polling if needed:

```bash
make run-no-telegram
```

## Test Locally

```bash
make test
```

Validate config:

```bash
make config-check
```

Check health:

```bash
make health
```

Send a sample request:

```bash
make invoke-sample
```

Main Telegram commands:

- plain text request intake
- `/confirm`
- `/approve REQ-...`
- `/reject REQ-...`
- `/needinfo REQ-...`
- `/cancel REQ-...`
- `/status REQ-...`
- `/history REQ-...`

## Deploy Preparation

- `.greennode.json` for AgentBase IAM
- Docker
- `.agentbase/deploy.env` for deploy-time overrides

Expected `.greennode.json`:

```json
{
  "client_id": "...",
  "client_secret": "..."
}
```

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
AI_PROMPT_VERSION=request-parse-v1
AI_MODEL=...
AI_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1
AI_API_KEY=...
AI_TIMEOUT_SECONDS=30
AI_MAX_TOKENS=250
AI_TEMPERATURE=0.0
AI_TOP_P=0.95
AI_PRESENCE_PENALTY=0.0
```

- `runtime.yaml` local-only
- `.greennode.json` local-only
- `runtime.example.yaml` secret-free
- local Docker build can use `make docker-build`

## Deploy To AgentBase

Use the AgentBase skills instead of running the helper scripts manually.

Typical prompts:

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

For redeploy:

```text
Use /agentbase-deploy to redeploy the existing runtime for this repo with `.agentbase/deploy.env`.
```

For status and endpoint checks:

```text
Use /agentbase-monitor to check runtime status and logs for this project.
```

```text
Use /agentbase-deploy to list endpoints for the current runtime.
```

Verify deployed runtime:

```bash
curl -s -i https://<endpoint-url>/health
```

Invoke:

```bash
curl -s -i -X POST https://<endpoint-url>/invocations \
  -H 'Content-Type: application/json' \
  -d '{"message":"for sample-object, change from disabled to enabled, ask @checker to approve","actor_name":"Requester One","actor_handle":"@requester"}'
```

## Notes

- LLM input assistance is optional and only assists request parsing.
- Workflow state stays rule-based even when AI is enabled.
- The AI request body follows AgentBase's OpenAI-compatible `/v1/chat/completions` pattern with `model`, `messages`, `max_tokens`, `temperature`, `top_p`, and `presence_penalty`.
