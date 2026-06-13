# marker-checker

Chat-first approval agent for a simple marker-checker workflow.

## What It Does

- requester sends a change request in Telegram or API
- agent normalizes the request and asks for confirmation
- approver approves, rejects, requests more info, or cancels
- request state and audit history are stored in Google Sheets
- optional LLM assistance helps parse free-form text and rewrite responses

## System Shape

```text
Telegram or API
    ->
Agent Runtime
    ->
Orchestrator
    -> RequestService / AuditService
    -> optional LLM assistance
    ->
Google Sheets
```

## Quick Start

Create local config:

```bash
cp runtime.example.yaml runtime.yaml
```

Install and set up:

```bash
make setup
```

Run locally:

```bash
make run
```

Run tests:

```bash
make test
```

Validate config only:

```bash
make config-check
```

## Main Config

Use:

- `runtime.yaml` for local config
- `runtime.example.yaml` as the committed template
- `.agentbase/deploy.env` for deploy-time overrides

Minimum values you need:

- `telegram.bot_token`
- `google_sheets.spreadsheet_id`
- one Google credential source:
  `service_account_file` or `service_account_json_base64`

Optional AI config:

- `ai.enabled`
- `ai.model`
- `ai.base_url`
- `ai.api_key`

## Main Commands

- plain text message: create or continue a request
- `/confirm`
- `/approve REQ-...`
- `/reject REQ-... reason`
- `/needinfo REQ-... note`
- `/cancel REQ-...`
- `/status REQ-...`
- `/history REQ-...`

## Deploy

Local image build:

```bash
make docker-build
```

AgentBase deploy inputs:

- `.greennode.json`
- `.agentbase/deploy.env`

Typical prompt:

```text
Use /agentbase-deploy to redeploy this repo as the existing Custom Agent.
Use `.agentbase/deploy.env` as the runtime env file.
Use AgentBase managed Container Registry.
Use linux/amd64.
Use the existing flavor and PUBLIC mode.
```

## Docs

- [docs/README.md](docs/README.md)
- [Product Overview](docs/product-spec/overview.md)
- [Workflow And Lifecycle](docs/product-spec/workflow-and-lifecycle.md)
- [Architecture](docs/technical-design/architecture.md)
- [Configuration And Integrations](docs/technical-design/configuration-and-integrations.md)
- [Implementation Plan](docs/delivery-plan/implementation-plan.md)
