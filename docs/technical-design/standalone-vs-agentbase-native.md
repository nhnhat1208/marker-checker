# Standalone vs AgentBase-Native

## Current Approach — Polling

The bot continuously polls Telegram in a background thread. AgentBase is used purely as a container host — the `/health` endpoint is the only one that sees any traffic.

```text
Container start → background thread polling Telegram ←→ Telegram API
AgentBase endpoint: /health only
```

**Is this the wrong design?**

Not wrong in a standalone context — this is the standard way to write a Telegram bot when self-hosting on any server. The code has no dependency on AgentBase and can run on a VPS, EC2, GCP, or any container host without modification. That is its biggest strength: **full portability**.

However, it is a poor fit for AgentBase: the container runs 24/7 without producing any invocations, billing does not reflect actual usage, and the entire platform ecosystem is bypassed.

---

## The AgentBase-Native Approach — Webhook

Telegram pushes each message to the AgentBase endpoint. Every message becomes an independent invocation.

```text
Telegram user → POST /invoke → AgentBase handler() → async reply
```

---

## Comparison

| | Polling | Webhook |
|---|---|---|
| Correct for standalone bot | Yes | Unnatural |
| Correct for AgentBase model | No | Yes |
| Scale-to-zero | No | Yes |
| Cross-thread complexity | Yes | No |
| Parallel LLM calls (`asyncio.gather`) | No | Yes |
| Local debugging | Easy | Requires ngrok |
| Session state | In-memory TTLCache | External store |

---

## What You Gain from the AgentBase Ecosystem After Migration

### Memory Service

Replaces in-memory TTLCache. Session state persists across restarts, survives container crashes, and works correctly when multiple replicas run. No more OOM risk from unbounded growth, no `RLock` needed.

**What to do:**

- Create a Memory instance via `/agentbase-memory`
- Replace `_pending_drafts`, `_pending_resubmit`, `_partial_drafts` TTLCache with Memory Service read/write calls
- Remove `cachetools` dependency and `_draft_lock`

### Monitor & Observability

Each message becomes a traceable invocation with its own log stream, latency measurement, and CPU/RAM breakdown. Currently only container-level stdout is available — impossible to correlate a slow response with a specific user or request.

**What to do:**
- Switch to webhook so each message produces an invocation record
- Use `/agentbase-monitor` to view per-invocation logs and latency dashboards
- No code changes needed beyond the webhook migration itself

### Identity Service

Store the LLM API key and Google service account credentials in AgentBase instead of baking them into env vars or the container image. Credentials are fetched at runtime, can be rotated without redeploying, and never appear in build artifacts.

**What to do:**
- Register an API key provider for the LLM key via `/agentbase-identity`
- Register an API key provider for the Google service account JSON via `/agentbase-identity`
- Replace env var reads in config with SDK credential injection (`requires_api_key` decorator or `IdentityClient.get_delegated_api_key`)
- Remove `AI_API_KEY` and `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` from `deploy.env`

### Usage-based Billing

Charges apply only when messages are actually processed. Currently the container runs 24/7 regardless of traffic volume.

**What to do:**
- Switch to webhook (billing follows invocations automatically)
- Set `min-replicas=0` in the runtime config

### Scale-to-zero

The container sleeps when there are no messages and wakes up on the first incoming webhook. Cold start on python-telegram-bot is under 2 seconds — acceptable for a low-traffic internal tool.

**What to do:**
- Switch to webhook
- Update runtime: `--min-replicas 0`
- Ensure `GET /health` responds quickly on startup so the platform marks the replica ready before Telegram retries the webhook

---

## Migration Steps

Must be done in order:

1. **Externalize session state** — migrate TTLCache to AgentBase Memory Service. This is the largest piece of work since the entire draft flow depends on in-memory state.
2. **Switch to webhook** — disable polling, add a route to receive Telegram POST requests, register `setWebhook`, remove `asyncio.to_thread` and `asyncio.run_coroutine_threadsafe`.
3. **Async LLM client** — replace `httpx.Client` with `httpx.AsyncClient` and use `asyncio.gather` for parallel LLM calls.

**When to migrate:**

- The bot feels slow and LLM latency needs to improve
- Expanding to additional channels (Zalo, web)
- Scale-to-zero is needed to reduce costs
- Starting a new agent from scratch — use webhook-native from the beginning
