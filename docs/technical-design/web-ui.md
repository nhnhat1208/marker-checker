# Web UI — marker-checker

Chat-first web interface for the marker-checker approval agent, bundled into the same Docker image as the Python backend.

---

## Personas

| Persona | Goal |
|---|---|
| **Requester** | Submit change requests, track status, resubmit after NEEDINFO |
| **Approver** | Review pending queue, approve / reject / needinfo in one action |
| **Both** | View request history and audit trail |

---

## Channel Model

The web UI is an independent channel, equivalent to Telegram — not an extension of it.

```text
Telegram channel  →  actor_handle = "@nhatnh3"            source.channel_id = "telegram"
Web channel       →  actor_handle = "nhatnh3@vng.com.vn"  source.channel_id = "web"
```

`RequestCoordinator` accepts `ActorContext` and `MessageSource` from any channel — the web layer only needs to construct these two objects from the Google session. No email ↔ Telegram handle mapping is needed. Requests created via web have `origin_channel_id = "web"`; approver notifications are sent to whichever channel the approver is using.

The `user_profiles` table (Neon) stores the Google display name and avatar for web users — it is not used for Telegram mapping:

```sql
CREATE TABLE IF NOT EXISTS user_profiles (
    email        TEXT PRIMARY KEY,
    display_name TEXT NOT NULL DEFAULT '',
    avatar_url   TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

---

## Tech Stack

### Backend

| Library | Role | Why |
| --- | --- | --- |
| **FastAPI** | HTTP server — OAuth routes, REST API, WebSocket, static file serving | Built on Starlette (zero migration cost), Pydantic validation included, dependency injection for auth middleware |
| **authlib** | Google OAuth 2.0 / OIDC client — authorization code flow, token exchange, ID token verification | Higher-level OAuth client than `google-auth`; integrates with HTTPX; handles PKCE + JWKS without boilerplate |
| **itsdangerous** | Signs the session cookie so the server can verify it was not tampered with | Allows logout invalidation unlike stateless JWT |
| **python-multipart** | Required by FastAPI to parse `multipart/form-data` on the OAuth callback | — |

### Frontend

| Library | Role | Why |
| --- | --- | --- |
| **React + Rsbuild** | UI framework + build tool | Rsbuild (Rspack/Rust) has no native `postinstall` scripts — solves pnpm strict build approval in Docker CI. Faster than Vite on large builds |
| **Tailwind CSS** | Utility-first CSS | Auto-detected by Rsbuild via `postcss.config.js`; CSS bundle < 10 KB after purge; no style conflicts with shadcn/ui |
| **shadcn/ui** | Accessible React components (Button, Badge, Dialog, Sheet, Avatar, Table, Tooltip) | Copies source into the project — fully customisable, no runtime overhead, built on Radix UI (WAI-ARIA) |
| **Zustand** | Client-side state — auth, message list, active request panel | Subscription model avoids full-tree re-renders on every message (Context API would cause visible lag) |
| **react-markdown + react-syntax-highlighter** | Render agent responses as Markdown with code highlighting | Agent outputs bullet lists, bold text, code blocks (request IDs, config values) |
| **@tanstack/react-query** | Data fetching + caching for REST endpoints | Handles loading/error/refetch state, background refresh, optimistic updates; better mutation support than SWR |

---

## Architecture

```text
Browser
  │
  ├─ GET  /                        → React SPA (index.html from /app/static)
  ├─ GET  /auth/google             → redirect to Google OAuth consent screen
  ├─ GET  /auth/callback           → exchange code, set httponly cookie, redirect /
  ├─ GET  /auth/logout             → clear cookie, redirect /
  ├─ GET  /api/me                  → { email, name, avatar_url }
  ├─ GET  /api/requests            → list requests for current user (as requester or approver)
  ├─ GET  /api/requests/:id        → request detail + audit events
  ├─ POST /api/requests/:id/action → approve / reject / needinfo (approver only)
  └─ WS   /ws/chat                 → bidirectional chat stream (authenticated via cookie)
               │
               ▼
       FastAPI (port 8080)
               │
               ├── session.py — verify signed cookie, inject WebUser
               │
               ▼
       RequestCoordinator
         ActorContext(handle=email, name=display_name)
         MessageSource(channel_id="web", ...)
               │
               ▼
       PostgresWorkflowStore
```

### WebSocket Protocol

Defined in `agent/src/agent/contracts/ws.py`, auto-generated to `frontend/src/lib/generated/ws-contract.ts` via `make contracts`. Never edit those files by hand.

```jsonc
// Client → Server (WsTextMessage | WsStructuredMessage | WsActionMessage)
{ "type": "message",            "text": "change nginx timeout from 30s to 60s, ask ops@vng.com.vn" }
{ "type": "structured_message", "draft": { "mode": "config_change", "request_format": "yaml", ... } }
{ "type": "action",             "op": "confirm" }
{ "type": "action",             "op": "discard" }

// Server → Client (WsTypingMessage | WsDoneMessage | WsErrorMessage)
{ "type": "typing" }
{ "type": "done",  "response": { ... }, "ui_response": { "kind": "...", "title": "...", ... } }
{ "type": "error", "message": "..." }
```

`WsTypingMessage` is sent before the agent starts processing (shows typing indicator). `WsDoneMessage.ui_response` carries a structured `UiResponse` for the frontend to render request cards, status badges, etc. The draft confirmation card is shown when `ui_response.kind == "confirmation_required"`.

For missing-field flows, `ui_response.kind == "missing_fields"` may also include a partial `draft` snapshot. The frontend uses that partial draft to render the same draft-style card shape with missing values highlighted inline, instead of switching to a separate diagnostic layout.

---

## Progress

### Phase 0 — Foundation ✅

- [x] Added `fastapi`, `authlib`, `itsdangerous`, `python-multipart` to `pyproject.toml`
- [x] Scaffolded `frontend/` — React + Rsbuild + Tailwind
- [x] Multi-stage Dockerfile: Node 22 + pnpm build → copy `frontend/dist` → `/app/static`
- [x] FastAPI mounts `StaticFiles("/app/static")`, SPA fallback to `index.html`
- [x] Routes: `/auth/google` → `/auth/callback` → httponly signed cookie
- [x] `/api/me` returns `{ email, name, avatar_url }`
- [x] `WS /ws/chat` — verifies cookie, creates `ActorContext(handle=email)`, pipes to `RequestCoordinator`
- [x] `user_profiles` table added to Postgres DDL in `postgres.py`
- [x] Auth guard: unauthenticated requests to `/api/*` and `/ws/*` return 401
- [x] `make run` still works (web routes disabled when `GOOGLE_CLIENT_ID`/`SECRET` are unset)
- [x] `WebConfig.enabled` derived from credentials presence — no explicit flag needed

### Phase 1 — Core Chat

- [ ] Sidebar (collapsed on mobile) + chat column layout — currently single-column only
- [x] Message list — auto-scroll to latest message
- [x] Timestamps on each message bubble
- [x] Message bubbles: user (right, accent) / agent (left, neutral) with agent avatar
- [x] User avatar / initials on user bubble
- [x] Typing indicator (3-dot animation) while waiting for agent response
- [x] Code blocks in messages — syntax highlighting + side-by-side diff view
- [ ] Full Markdown rendering — bullets, bold, italic, headers (currently only code blocks; other markdown renders as raw text)
- [x] **Confirm / Discard buttons on draft card** — draft confirmation now renders as a structured card with direct action buttons wired to WS draft actions
- [x] Status badge inline — APPROVED / REJECTED / NEEDS_INFO / PENDING color-coded
- [x] Need-info guidance — when the agent asks for more info, the UI shows a short hint plus a normal draft-style card with partial values preserved and missing fields highlighted inline
- [x] Auto-reconnect with exponential backoff (1s → 30s); connection status dot in header
- [x] `Enter` to send, `Shift+Enter` for newline (spec said `Cmd+Enter` but `Enter` is standard chat UX)
- [x] Google profile in header: avatar + name + theme picker + language toggle + logout dropdown
- [x] Card-level VI / EN copy — draft / request / need-info cards, action labels, status labels, and paging/search copy are routed through `i18next`

### Phase 2 — Request Dashboard

- [ ] Sidebar navigation: **Chat** / **My Requests** / **Pending Approvals**
- [ ] **My Requests** page: table with request_id, target, change summary, status badge, updated_at; filter tabs (All / Pending / Resolved); search by target label; click row → slide-out detail panel; poll every 10s
- [ ] **Pending Approvals** page: requests waiting for the current user's decision; inline Approve / Reject / Need Info buttons; Reject and Need Info open a note modal; action calls `POST /api/requests/:id/action`
  Phase 1 note: chat review cards now expose inline Approve / Reject / Need Info actions for the current approver.
- [ ] **Request Detail panel**: full request fields, audit trail timeline, resolved by / at, copy request_id button

### Phase 3 — Polish

- [x] Theme switcher — light / dark / dim / dracula / system, persisted to `localStorage`, reacts to OS preference changes
- [x] Language toggle — VI / EN via i18next, persisted to `localStorage`
- [ ] Mobile responsive layout — approvers can act from their phone
- [ ] Toast notifications on action success / failure
- [ ] Error boundary — one component crashing does not take down the whole page
- [ ] Keyboard navigation: `Esc` closes panel, arrow keys navigate table (depends on Phase 2)

---

## File Structure

```text
marker-checker/
├── frontend/                            ← React app (Rsbuild + Tailwind + pnpm)
│   ├── src/
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   │   ├── ChatComposer.tsx         ← message input bar
│   │   │   │   ├── ChatHeader.tsx           ← chat panel header
│   │   │   │   ├── ChatEmptyState.tsx       ← empty state
│   │   │   │   ├── MessageBubble.tsx        ← user / agent bubble + markdown
│   │   │   │   ├── StructuredAgentBubble.tsx← structured response card (draft, status, etc.)
│   │   │   │   └── TypingIndicator.tsx
│   │   │   └── ui/                          ← shadcn/ui component copies
│   │   │       ├── button.tsx
│   │   │       └── tooltip.tsx
│   │   ├── contexts/
│   │   │   └── theme.tsx                    ← dark/light theme context
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts              ← connect, reconnect, send, dispatch typed messages
│   │   ├── i18n/
│   │   │   └── index.ts                     ← i18next setup (i18next-http-backend)
│   │   ├── lib/
│   │   │   ├── chatTypes.ts                 ← generated WS contract re-exports + chat aliases
│   │   │   ├── chat-ui/                     ← structured bubble constants, response derivation, message transforms
│   │   │   ├── codeDiff.ts                  ← code diff helpers
│   │   │   ├── utils.ts                     ← shadcn/ui cn() utility
│   │   │   └── generated/
│   │   │       └── ws-contract.ts           ← auto-generated TypeScript interfaces (make contracts)
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx
│   │   │   └── LoginPage.tsx
│   │   └── App.tsx                          ← router, auth guard
│   ├── scripts/
│   │   └── gen-contracts.mjs                ← reads asyncapi.yaml, writes ws-contract.ts
│   ├── index.html
│   ├── package.json
│   ├── rsbuild.config.ts
│   ├── postcss.config.js
│   └── tailwind.config.ts
│
├── agent/src/agent/
│   ├── contracts/
│   │   └── ws.py                            ← WS message models, WsContract, WsChatHandlerBase
│   └── web/
│       ├── server.py                        ← create_web_app(), mount routes + StaticFiles
│       ├── auth.py                          ← /auth/google, /auth/callback, /auth/logout
│       ├── session.py                       ← verify signed cookie, inject WebUser
│       ├── models.py                        ← web-layer Pydantic models
│       ├── notifier.py                      ← WebSocket broadcast helpers
│       ├── chat_ws.py                       ← ChatWsHandler (implements WsChatHandlerBase)
│       └── api.py                           ← /api/me, /api/requests, /api/requests/:id/action
│
├── contracts/
│   └── asyncapi.yaml                        ← auto-generated from ws.py (make contracts)
│
├── Dockerfile                               ← multi-stage: Node 22 build → Python 3.11 slim
└── runtime.yaml
```

**Phase 2 components not yet built:** `requests/RequestTable.tsx`, `requests/RequestDetail.tsx`, `requests/ActionModal.tsx`, `layout/Sidebar.tsx`, `layout/Header.tsx`, `pages/MyRequestsPage.tsx`, `pages/ApprovalsPage.tsx`.

---

## Configuration

Web UI has no explicit flag in `runtime.yaml`. It is enabled automatically when both `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are set:

```python
# agent/src/agent/config.py
class WebConfig(_EnvFirstSettings):
    model_config = SettingsConfigDict(env_prefix="GOOGLE_")
    client_id: str = ""       # GOOGLE_CLIENT_ID
    client_secret: str = ""   # GOOGLE_CLIENT_SECRET
    redirect_uri: str = ""    # GOOGLE_REDIRECT_URI (auto-derived from GREENNODE_ENDPOINT_URL if empty)
    session_secret: str = ""  # GOOGLE_SESSION_SECRET — signs the session cookie

    @property
    def enabled(self) -> bool:
        return bool(self.client_id.strip() and self.client_secret.strip())
```

To enable: set `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_SESSION_SECRET` in `deploy.env`.
To disable: remove those vars — no change to `runtime.yaml` needed.

---

## Out of Scope

- Admin panel (view all users / all requests regardless of role)
- File attachments in chat
- Email notifications
- Audit log export (CSV / PDF)
- Linking web identity to Telegram identity

---

## Current UX Notes

- The structured agent bubble now has three primary card modes:
  - draft confirmation card
  - request status / review card
  - missing-info card rendered with the same draft-card visual language
- Missing info is no longer displayed as a separate inspector/debug panel. Instead, the frontend renders the partial draft snapshot and marks unresolved fields inline in the same card structure.
- The “Add missing details” action inserts a guided fill-in template into the composer and hides once the user has already replied after that missing-info prompt.
- VI / EN localization currently covers the main chat surface:
  - header
  - empty state
  - composer
  - draft / request / missing-info cards
  - inline action buttons
  - search and paging controls inside structured bubbles
