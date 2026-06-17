# Web UI

The web UI is a second chat channel for the same approval workflow. It is served from the same container as the Python backend and talks to the workflow through an authenticated WebSocket.

## What Exists Today

- Google OAuth login and logout
- signed session cookie for authenticated browser sessions
- authenticated `GET /api/me`
- authenticated `WS /ws/chat`
- single-page React chat UI
- structured agent cards for confirmation, status, review actions, and missing fields
- VI / EN localization on the main chat surface
- theme switching and reconnect-aware connection state

## Channel Model

The web UI is its own channel, not a thin layer on top of Telegram.

```text
Telegram channel  -> actor_handle = "@nhatnh3"         source.channel_id = "telegram"
Web channel       -> actor_handle = "nhatnh3@vng.com"  source.channel_id = "web"
```

The web layer builds `ActorContext` and `MessageSource` from the signed Google session, then hands the request to `RequestCoordinator`. Requests created on the web keep `origin_channel_id = "web"`.

## Runtime Shape

```text
Browser
  -> GET /auth/google
  -> GET /auth/callback
  -> GET /auth/logout
  -> GET /api/me
  -> WS  /ws/chat
         |
         v
FastAPI routes inside the main runtime
         |
         v
RequestCoordinator
         |
         v
Configured workflow store
```

The frontend bundle is built from `frontend/` and served as static files by the backend in production. In local development, the Rsbuild dev server proxies `/api`, `/auth`, and `/ws` to `http://localhost:8080`.

## WebSocket Contract

The contract is defined in `agent/src/agent/contracts/ws.py` and generated into:

- `contracts/asyncapi.yaml`
- `frontend/src/lib/generated/ws-contract.ts`

Do not edit the generated files by hand. Run:

```bash
make contracts
```

Current client message families:

- `message` for free-text chat input
- `structured_message` for a full structured draft payload
- `action` for confirm, discard, approve, reject, and need-info actions

Current server message families:

- `typing`
- `done`
- `error`

## Contract Notes

The current contract is intentionally small, but there are a few rules maintainers need to keep in mind:

- `action` messages reuse one shape for both draft actions and review actions
- `confirm` and `discard` do not require a `request_id`
- `approve`, `reject`, and `needinfo` expect `request_id`, with optional `note`
- `done` messages can carry both a plain `response` payload and a structured `ui_response`
- `ui_response` is the typed envelope the frontend uses for cards, draft previews, missing-field prompts, and request lists
- `structured_message` carries the full structured draft, including `before` and `after` code sections with format metadata

Contract safety rules:

- update `agent/src/agent/contracts/ws.py` first, not the generated files
- run `make contracts` after every contract change
- keep `ChatWsHandler` aligned with `WsChatHandlerBase`; the abstract base class is part of the enforcement mechanism, not just documentation
- if a new client message type is added, the backend must implement a matching handler method before startup will succeed

## Current Frontend Shape

The shipped UI is intentionally narrow in scope: one authenticated chat page plus one login page.

Key files:

- `frontend/src/App.tsx` — auth bootstrap, chooses login page or chat page
- `frontend/src/pages/LoginPage.tsx` — unauthenticated landing page
- `frontend/src/pages/ChatPage.tsx` — main chat surface
- `frontend/src/hooks/useChatSession.ts` — session state and WS orchestration
- `frontend/src/hooks/useWebSocket.ts` — socket lifecycle and reconnect behavior
- `frontend/src/components/chat/` — message bubbles, cards, composer, header

## Authentication Notes

Web UI is enabled automatically when these env vars are set:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_SESSION_SECRET`

`GOOGLE_REDIRECT_URI` is optional. If it is empty, the backend derives the callback URL from the incoming request.

For local development:

- backend runs on `http://localhost:8080`
- frontend dev server runs on `http://localhost:3000`
- `make run` sets `GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback` so the browser returns through the dev server proxy

## Current Limitations

Not implemented yet:

- request dashboard pages
- dedicated request detail page or side panel
- REST endpoints for request listing and moderation outside chat
- admin or reporting views
- identity linking between web users and Telegram handles

## Out of Scope

- file attachments in chat
- email notifications
- audit export workflows
