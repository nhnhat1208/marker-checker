# Delivery Roadmap

---

## Phase 0 — Core Delivery ✓ (Deployed)

**Current deployment:** v14 on GreenNode AgentBase Runtime, polling-based, single replica.

### What's Working

- parse request from free-form text (Vietnamese or English), show normalized summary, require `/confirm` before submit
- approve, reject, need info, cancel, resubmit after need info
- status lookup, history lookup, request search by target name
- LLM assistance for parsing and response wording (optional, falls back gracefully)
- Google Sheets persistence with audit trail
- rolling deploy Conflict retry (new container recovers within 3 minutes)
- config robustness — empty env vars from platform are ignored

### What's Out of Scope (Deferred)

- web UI
- group-chat workflow
- RBAC
- reminder automation
- multi-channel (Zalo, web)
- direct mutation of external systems

---

## AgentBase-Native Migration

Move from a 24/7 polling container to a stateless webhook-per-invocation design.

**Pre-conditions:** agent is deployed and working, Google Sheets persistence is confirmed stable.

See [standalone-vs-agentbase-native.md](../technical-design/standalone-vs-agentbase-native.md) for the full tradeoff analysis.

---

### Phase 1 — Externalize Session State

All in-memory state must survive container restarts before switching to webhook.

| State | Current | Target | TTL |
| --- | --- | --- | --- |
| `_pending_drafts` | `TTLCache` in `DraftManager` | Memory Service | 1 hour |
| `_pending_resubmit` | `TTLCache` in `DraftManager` | Memory Service | 24 hours |
| `_partial_drafts` | `TTLCache` in `DraftManager` | Memory Service | 5 minutes |
| `_chat_registry` | `LRUCache` in `TelegramAdapter` | Google Sheets worksheet | no TTL |

`_chat_registry` goes to Sheets (not Memory Service) because it maps `@handle → chat_id` for approver DMs and must be permanently persistent.

**Files changed:** `draft_manager.py` (delete), `request_coordinator.py`, `persistence/google_sheets.py`, `adapters/telegram_adapter.py`, `runtime.py`, `pyproject.toml` (remove cachetools).

**Validation:**

- submit a request → kill container → restart → `/confirm` must still work
- NEEDINFO a request → restart → resubmit must still route correctly
- approver DMs must arrive after container restart

---

### Phase 2 — Switch to Webhook

**What changes in `telegram_adapter.py`:**

- remove `_polling_thread`, `_loop`, `start_polling()`, `_run_polling()`
- add `async def process_update(update_data: dict)` — receives raw JSON from webhook POST
- `notify_approver` becomes `async` — direct `await bot.send_message()`, no thread bridge

**What changes in `main.py`:**

```python
@app.route("/telegram-webhook", methods=["POST"])
async def telegram_webhook(request):
    data = await request.json()
    await telegram_adapter.process_update(data)
    return {"ok": True}
```

Register webhook on startup using `GREENNODE_ENDPOINT_URL` (auto-injected by runtime).

**Validation:** end-to-end message flow, approver DM, container restart with no lost drafts.

---

### Phase 3 — Async LLM Client

Replace `httpx.Client` with `httpx.AsyncClient`. Run classify and assist concurrently:

```python
intent, assisted = await asyncio.gather(
    assistant.classify_intent(text),
    assistant.assist_request_text(text),
)
```

Currently sequential (~1-3s). With gather: ~0.5-1.5s.

**Files changed:** `ai/llm_client.py`, `ai/assistant.py`, `request_coordinator.py`, `adapters/telegram_adapter.py` (remove remaining `asyncio.to_thread`).

---

### Phase 4 — Identity Service (Optional)

Remove `AI_API_KEY` and `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` from `deploy.env`. Store in AgentBase Identity Service and fetch at runtime via `IdentityClient`. Can be done independently after Phase 2.

---

### Migration Order

```text
Phase 1 → Phase 2 → Phase 3
                 └── Phase 4 (any time after Phase 2)
```
