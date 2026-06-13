# AgentBase Execution Plan

## Purpose

This document turns the current decisions into a practical execution path on AgentBase and VNG Cloud.

The chosen direction is intentionally small:

- one `Custom Agent` runtime
- one Telegram bot
- one Google Sheets file as shared persistence
- no separately deployed database

## Chosen Platform Path

Use:

- `AgentBase Custom Agent`
- `AgentBase managed Container Registry`
- `Telegram 1:1`
- `Google Sheets`
- `AgentBase Monitor`

Do not use now:

- `OpenClaw`
- `AgentBase Memory` for workflow state
- `MCP`
- `LangChain` or `LangGraph`
- separate database deployment

## Why This Path

The product needs custom workflow logic, but deployment should stay light.

This path gives:

- custom workflow in one Python service
- shared persistence without a DB rollout
- simple Telegram integration
- low operational overhead

## Minimum Components

| Need | Component | Required Now | Notes |
|---|---|---|---|
| Run the service | `AgentBase Runtime / Custom Agent` | Yes | main deployment target |
| Store image | `AgentBase managed Container Registry` | Yes | default image path |
| First channel | `Telegram bot` | Yes | first adapter only |
| Shared persistence | `Google Sheets` | Yes | requests, audit, conversation links |
| Logs and health | `AgentBase Monitor` | Yes | post-deploy verification |
| Platform IAM | service account | Yes | runtime and registry access |
| External auth management | `AgentBase Identity/Auth` | No | only if needed later |
| LLM access | `GreenNode AI Platform` | No | later for AI review only |

## What To Build

Build one Python service with:

1. `TelegramAdapter`
2. `AgentOrchestrator`
3. `RequestService`
4. `AuditService`
5. `WorkflowStore`
6. `GoogleSheetsWorkflowStore`

## What Must Be Set Up

### AgentBase

- IAM credentials
- container registry access
- one runtime deployment target

### Telegram

- one bot token
- agreed approver mention format

### Google Sheets

- one shared spreadsheet
- one Google service account
- spreadsheet shared with the service-account email
- credential source for local and deployed runtime

## Required Runtime Configuration

- `runtime.yaml` as the main runtime configuration
- `TELEGRAM_BOT_TOKEN` as an optional secret override
- `GOOGLE_SERVICE_ACCOUNT_FILE` or `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` as the credential source

## Delivery Sequence

### Step 1: Start From Locked Decisions

Use the already locked first-release direction from [Scope And Channel Decision](../technical-design/scope-and-channel-decision.md) and [Implementation Plan](./implementation-plan.md).

### Step 2: Prepare External Dependencies

Prepare:

- Telegram bot token
- spreadsheet ID
- service-account credentials
- AgentBase IAM and registry access

### Step 3: Build The Service

Implement only:

- request intake
- requester confirmation
- approve, reject, needs-info, cancel
- lookup by request ID
- audit persistence

### Step 4: Validate Locally

Verify:

- runtime starts
- Google Sheets connection works
- worksheets are created
- request and audit rows are written correctly
- restart still reads old state

### Step 5: Deploy

Use:

- one Dockerfile
- one managed registry image
- one `Custom Agent` runtime
- one replica first

### Step 6: Verify After Deploy

Check:

- runtime is `ACTIVE`
- health endpoint works
- Telegram end-to-end flow works
- spreadsheet rows are written correctly
- logs are visible

## Minimum Deploy Footprint

- `1` custom agent runtime
- `1` managed container image repository
- `1` Google spreadsheet
- `1` Telegram bot token
- `1` runtime environment config set

Future changes should be added only when they become active delivery scope.
