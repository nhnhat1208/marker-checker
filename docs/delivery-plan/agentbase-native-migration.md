# Migration Plan: Standalone → AgentBase-Native

## Goal

Move from a 24/7 polling container to a stateless webhook-per-invocation design that uses the AgentBase ecosystem correctly.

## Pre-conditions

- Agent is deployed and working on AgentBase Runtime
- Google Sheets persistence is confirmed stable
- Team is not actively using the bot during migration window

---

## Phase 1 — Externalize Session State

This is the hardest phase and must be done before anything else. All in-memory state must survive container restarts and work across multiple replicas.

### What needs to move out

| State | Current | Target | TTL |
|---|---|---|---|
| `_pending_drafts` | `TTLCache[str, PendingDraft]` | Memory Service | 1 hour |
| `_pending_resubmit` | `TTLCache[str, str]` | Memory Service | 24 hours |
| `_partial_drafts` | `TTLCache[str, tuple[str, ParsedRequest]]` | Memory Service | 5 minutes |
| `_chat_registry` | `LRUCache[str, str]` | Google Sheets new worksheet | no TTL |

### Why `_chat_registry` goes to Google Sheets, not Memory Service

`_chat_registry` maps `@handle → telegram_chat_id`. It is needed for `notify_approver` — to DM an approver when someone else's request gets submitted. With scale-to-zero, a container restart would wipe this mapping, and the approver would not receive notifications until they send a message to the bot again. Google Sheets already exists and is the right fit: persistent, no TTL, queryable.

### Key design decisions

**Serialization** — `PendingDraft` and `ParsedRequest` are TypedDicts. They serialize cleanly to JSON. Memory Service stores arbitrary string values, so `json.dumps` / `json.loads` works.

**Key schema for Memory Service:**

```
pending_draft:{handle}        → JSON of PendingDraft
pending_resubmit:{handle}     → request_id string
partial_draft:{handle}        → JSON of {original_text, parsed}
```

**Locking** — `_draft_lock` (`RLock`) exists only because TTLCache is not thread-safe. Memory Service calls are I/O-bound and inherently serialized per key. Remove the lock entirely once Memory Service is in place.

### Files changed

- `orchestrator.py` — replace all TTLCache get/set/pop with `MemoryClient` async calls; remove `_draft_lock`, `cachetools` import
- `persistence/google_sheets.py` — add `save_chat_id(handle, chat_id)` and `get_chat_id(handle)` methods, new `chat_registry` worksheet
- `adapters/telegram_adapter.py` — replace `_chat_registry` LRUCache with calls to new Sheets methods
- `runtime.py` — pass `MemoryClient` into orchestrator
- `pyproject.toml` — remove `cachetools`

### Risk

Memory Service adds network latency to every state read/write. Current TTLCache is microseconds; Memory Service will be ~10-50ms. This adds latency to every message that touches draft state. Acceptable for an internal tool. Mitigate by batching reads where possible (read draft + resubmit state in one call if the API supports it).

### Validation

- Submit a request, kill and restart the container, then `/confirm` — draft must still be there
- NEEDINFO a request, restart, then reply — resubmit must still route correctly
- Approver DMs must arrive after container restart

---

## Phase 2 — Switch to Webhook

Telegram stops being polled and starts pushing. Each message becomes a POST to the AgentBase endpoint.

### What changes in `telegram_adapter.py`

Remove entirely:
- `_polling_thread`, `_loop`, `start_polling()`, `_run_polling()`
- `asyncio.run_coroutine_threadsafe` in `notify_approver` and `_send_message`

Add:
- `async def process_update(self, update_data: dict) -> None` — receives raw JSON from webhook POST, parses into PTB `Update`, dispatches through `Application`
- `notify_approver` becomes `async def notify_approver(...)` — direct `await bot.send_message()`, no cross-thread bridge needed

### What changes in `main.py`

Add a webhook route alongside the AgentBase entrypoint:

```python
@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook(request):
    data = await request.json()
    await telegram_adapter.process_update(data)
    return {"ok": True}
```

Add startup hook to register `setWebhook` with Telegram:

```python
await bot.set_webhook(url=f"{endpoint_url}/telegram-webhook")
```

`GREENNODE_ENDPOINT_URL` is auto-injected by AgentBase Runtime — use it directly.

### What changes in `runtime.py`

- Remove `start_background_services()` call
- Wire `notify_approver` as async callback (no threading bridge)

### Files changed

- `adapters/telegram_adapter.py` — remove polling infrastructure, add `process_update`, make `notify_approver` async
- `main.py` — add webhook route, register `setWebhook` on startup
- `runtime.py` — remove background services call, update callback wiring
- `runtime.yaml` — set `TELEGRAM_POLLING_ENABLED: false`

### Risk

**Webhook registration race** — `setWebhook` must complete before Telegram starts sending updates. Wrap in startup hook, not in `__init__`. If registration fails on startup, log clearly and continue — Telegram will retry delivery.

**Double-processing** — if both polling and webhook are active at the same time (during transition), some updates may be processed twice. Disable polling (`TELEGRAM_POLLING_ENABLED: false`) before registering the webhook.

**`_chat_registry` cold start** — after Phase 1, registry is in Sheets. But if an approver has never interacted with the bot, `notify_approver` will still fail silently. This is the same behaviour as today — not a regression.

### Validation

- Send a message to the bot and confirm it responds
- Submit a request — approver should receive DM
- `/status`, `/mypending`, `/myapprovals` all work
- Container restart does not lose pending drafts (covered by Phase 1)

---

## Phase 3 — Async LLM Client

With a fully async request handler, LLM calls can run concurrently with `asyncio.gather` instead of sequentially in a thread pool.

### What changes in `ai/llm_client.py`

Replace `httpx.Client` with `httpx.AsyncClient`. All methods become `async def`. The persistent client is created once and reused — connection pooling still applies.

### What changes in `ai/assistant.py`

All methods become `async def`. The key optimization: for new requests where `classify_intent` returns incomplete fields, run `classify_intent` and `assist_request_text` concurrently:

```python
classify_task, assist_task = await asyncio.gather(
    self.classify_intent(text),
    self.assist_request_text(text),
)
```

Currently these run sequentially: ~1-3s total. With gather: ~0.5-1.5s (slowest of the two).

### What changes in `orchestrator.py`

All methods that call the assistant become `async def`. The calling chain propagates up to the Telegram handlers — but since Phase 2 already makes handlers async, this is a natural continuation.

### Files changed

- `ai/llm_client.py` — `httpx.Client` → `httpx.AsyncClient`, all methods async
- `ai/assistant.py` — all methods async, add `asyncio.gather` for classify + assist
- `orchestrator.py` — all public methods async
- `adapters/telegram_adapter.py` — remove remaining `asyncio.to_thread` wrappers (already direct `await`)

### Risk

Making `orchestrator.py` fully async is a large diff. The orchestrator is also called from `runtime.py` via the AgentBase sync handler. AgentBase already wraps sync handlers with `run_in_executor` — but an async orchestrator needs an async handler in `main.py`. This is a straightforward change but touches many call sites.

### Validation

- New request flow end-to-end: latency should be noticeably lower
- Run test suite — all 34 tests must pass (tests will need async fixtures updated)

---

## Phase 4 — Identity Service (Optional)

Remove `AI_API_KEY` and `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` from `deploy.env`. Store them in AgentBase Identity Service and fetch at runtime.

### What to do

- Register LLM API key via `/agentbase-identity` as an API key provider
- Register Google service account JSON via `/agentbase-identity` as an API key provider
- In config loading, replace env var reads with `IdentityClient.get_delegated_api_key(provider_name)`
- Remove both secrets from `deploy.env` and redeploy

### Risk

If Identity Service is unavailable at startup, the agent fails to boot. Add a fallback: try Identity Service first, fall back to env var if present. This keeps local development working without Identity Service.

### Validation

- Remove keys from `deploy.env`, deploy, confirm bot still works
- Rotate LLM API key via Identity Service — bot picks up new key on next restart without redeploying

---

## Migration Order and Dependencies

```
Phase 1 (Session State)
  └── Phase 2 (Webhook)
        └── Phase 3 (Async LLM)
              └── Phase 4 (Identity) ← independent, can be done any time after Phase 2
```

Phases 1 and 2 are required to gain meaningful benefit. Phase 3 is a latency optimization. Phase 4 is a security improvement.

Each phase can be deployed independently. Phase 1 in particular can be rolled out while still using polling — validate state persistence before touching the network layer.
