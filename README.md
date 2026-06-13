# marker-checker

AgentBase Custom Agent scaffold for a simple marker-checker approval workflow.

## Purpose

This scaffold is built for one narrow, useful flow:

- requester sends a change request in Telegram
- approver reviews and resolves it
- the system stores request state and audit history in Google Sheets
- the runtime runs as one AgentBase Custom Agent

This scaffold intentionally does not include:

- AI review assistance
- group-chat workflow
- RBAC
- AgentBase Memory
- additional channels

## Stack

- `greennode-agentbase`
- `python-telegram-bot`
- `gspread`
- `google-auth`
- `PyYAML`
- `pydantic`

## Project Layout

```text
.
├── docs/
├── marker_checker_agent/
│   ├── domain/
│   ├── adapters/
│   ├── request_parser.py
│   ├── persistence/
│   └── services/
├── runtime.example.yaml
├── main.py
├── Dockerfile
└── requirements.txt
```

Layout intent:

- `domain/` keeps workflow records and enums
- `request_parser.py` keeps request-intake parsing separate from orchestration
- `services/` keeps approval workflow rules
- `persistence/` keeps storage abstractions plus Google Sheets mapping and store logic

## Configuration

Primary configuration lives in `runtime.yaml`.

Start from the example file:

```bash
cp runtime.example.yaml runtime.yaml
```

Main place to edit:

- `runtime.yaml` for application, workflow, Telegram, and Google Sheets settings

Typical local values to fill:

- `google_sheets.spreadsheet_id` in `runtime.yaml`
- one Google service-account credential source
  - `GOOGLE_SERVICE_ACCOUNT_FILE` for local development
  - or `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` for deployed runtime
- `telegram.bot_token` in `runtime.yaml`, or `TELEGRAM_BOT_TOKEN` as a runtime override

## Google Sheets Setup

1. Create one Google Sheet for the service.
2. Enable `Google Sheets API` for the Google Cloud project used by the service account.
3. Create or reuse a Google service account with Sheets API access.
4. If you keep the current scopes, also enable `Google Drive API`.
5. Share the spreadsheet with the service-account email as editor.
6. Put the spreadsheet ID in `runtime.yaml` under `google_sheets.spreadsheet_id`.
7. Provide credentials through either:
   - `google_sheets.service_account_file` in `runtime.yaml`
   - or `google_sheets.service_account_json_base64` in `runtime.yaml`
   - or the matching environment variables if your deploy environment prefers runtime overrides

The app auto-creates these worksheets when enabled:

- `requests`
- `audit_events`
- `request_conversations`

## Local Setup

```bash
.venv/bin/python -m pip install -r requirements.txt
cp runtime.example.yaml runtime.yaml
```

If you do not have `.venv` yet:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp runtime.example.yaml runtime.yaml
```

Then update `runtime.yaml` with your real runtime values.

## Run Locally

```bash
python main.py
```

What should happen:

- AgentBase health server starts on `0.0.0.0:8080`
- Google Sheets worksheets are prepared if auto-create is enabled
- Telegram polling starts if `telegram.enabled: true`, `telegram.polling_enabled: true`, and a bot token is present

## Smoke Test

Run the offline workflow smoke test:

```bash
.venv/bin/python -m unittest discover -s tests -v
```

This test does not call Telegram or Google Sheets. It verifies the local request lifecycle using an in-memory store.

## Current Commands

Telegram skeleton currently supports:

- plain text request intake
- `/confirm`
- `/approve REQ-... note`
- `/reject REQ-... reason`
- `/needinfo REQ-... note`
- `/cancel REQ-... note`
- `/status REQ-...`
- `/history REQ-...`

## Notes

- Persistence is intentionally behind a `WorkflowStore` abstraction.
- `Google Sheets` is the first backend because it avoids deploying a separate database.
- If request volume, concurrency, or reporting needs grow later, the storage backend can move to a SQL database without rewriting workflow rules.
- The approver-notification callback is still a scaffold hook. Real Telegram routing to a specific approver chat needs a confirmed chat-ID strategy.
