<p align="center">
  <img src="frontend/public/favicon.svg" alt="Marker Checker" width="80" height="80" />
</p>

<h1 align="center">Marker Checker</h1>

<p align="center">Turning approval workflows into simple conversations.</p>

Many teams still handle requests and approvals through manual, fragmented steps: users need to know the process, provide the right context, find the right approver, and keep track of what happened afterward. As organizations grow, that context gets scattered across chat, tickets, spreadsheets, and memory.

Marker Checker is built on AgentBase for Engineering, Operations, IT, and Project Management teams that regularly deal with request, approval, and change workflows. Instead of making users learn the workflow first, it lets them describe what they need in plain language. The agent gathers missing details, structures the request, routes it for approval, and keeps the full history searchable.

The same workflow can be used from Telegram, the web chat UI, or a direct API invocation:

1. requester describes a change
2. agent normalizes it and asks for confirmation if needed
3. approver approves, rejects, or asks for more info
4. request state, discussion, and audit history are stored in the configured backend

## What It Covers

- Telegram intake and approval commands
- Google-authenticated web chat over WebSocket
- API invocation entrypoint for automation or testing
- request confirmation, needs-info loop, and audit trail
- PostgreSQL as the default store, with Google Sheets as a legacy fallback
- optional LLM assistance for parsing and response wording

## Why It Matters

- lowers the effort needed to create a complete request
- reduces back-and-forth around approval context and ownership
- keeps request history, reviewer decisions, and follow-up discussion in one place
- makes approval decisions easier to trace and improve over time

## Example Flow

Example requester message:

```text
enable feature-X on api-gateway, ask annie@example.com to approve
```

Example approver actions:

```text
/approve REQ-1234 looks good
/reject REQ-1234 missing rollback plan
/needinfo REQ-1234 please include rollback steps
```

Example query flows:

```text
/status REQ-1234
history REQ-1234
my requests
pending approvals
search api-gateway
```

## Where It Can Grow

- recommend likely approvers based on prior requests and team patterns
- flag missing context or weak requests before they reach reviewers
- suggest approval paths from policy and historical decisions
- connect approved requests to downstream execution systems when needed

## Project Layout

- `agent/` Python runtime, workflow logic, adapters, persistence
- `frontend/` React web chat UI
- `contracts/` generated AsyncAPI contract
- `docs/` product and technical documentation
- `tests/` unit tests
- `runtime.yaml` committed non-secret config
- `deploy.example.env` template for runtime secrets and deploy variables

## Getting Started

Prerequisites:

- Python 3.11+
- `uv`
- Node.js 22+ and `pnpm` for the frontend

Create local config:

```bash
cp deploy.example.env deploy.env
```

For local Telegram development, create or update `runtime.local.yaml` with polling mode:

```yaml
telegram:
  mode: polling
```

Install dependencies:

```bash
make install
pnpm --dir frontend install
```

Run the backend:

```bash
make run
```

Run the frontend dev server:

```bash
make frontend
```

## Telegram Testing

For local Telegram testing:

- create a bot with BotFather and put its token in `deploy.env` as `TELEGRAM_BOT_TOKEN`
- keep `telegram.mode: polling` in `runtime.local.yaml`
- run `make run`, then send `/start` to the bot from each test account

Detailed setup, notification caveats, and a manual end-to-end flow are documented in [Configuration, Integrations](docs/technical-design/configuration-integrations.md).

Useful commands:

- `make test` — run unit tests
- `make contracts` — regenerate AsyncAPI and TypeScript WS types
- `make config-check` — validate config loading
- `make smoke` — verify PostgreSQL connectivity
- `make invoke-sample` — send a sample local invocation

## Configuration

Core files:

- `runtime.yaml` — committed defaults and non-secret settings
- `runtime.local.yaml` — local overrides, typically gitignored
- `deploy.env` — secrets and deploy-time env vars, not committed
- `.greennode.json` — AgentBase IAM credentials for deploy tooling

Typical local setup needs:

- `TELEGRAM_BOT_TOKEN`
- `POSTGRES_DSN`
- either valid AI settings (`AI_MODEL`, `AI_API_KEY`) or `AI_ENABLED=false`

Enable the web UI by setting:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_SESSION_SECRET`

Deployment also needs:

- `IMAGE_REPO`
- `RUNTIME_ID`
- `FLAVOR`
- `.greennode.json` copied from `.greennode.example.json`

Detailed config notes live in [Configuration, Integrations](docs/technical-design/configuration-integrations.md).

## Entry Points

- Telegram for free-text intake and approval shortcuts
- Web chat UI over Google-authenticated WebSocket sessions
- Direct API invocation for automation and local testing

Route and command details live in [Architecture](docs/technical-design/architecture.md) and [Configuration, Integrations](docs/technical-design/configuration-integrations.md).

## Deploy

Build, push, and update the AgentBase runtime:

```bash
make deploy
```

Build the container image only:

```bash
make docker-build
```

## Further Reading

- [Documentation Guide](docs/README.md)
- [Product Overview](docs/product-spec/overview.md)
- [Workflow Lifecycle](docs/product-spec/workflow-lifecycle.md)
- [Data Model Audit](docs/product-spec/data-model-audit.md)
- [Architecture](docs/technical-design/architecture.md)
- [Architecture Diagrams](docs/technical-design/architecture-diagrams.md)
- [Web UI](docs/technical-design/web-ui.md)
- [Configuration, Integrations](docs/technical-design/configuration-integrations.md)
