# Standalone vs AgentBase-Native

## Current Design — Polling

The bot polls Telegram in a background daemon thread. AgentBase is used as a container host only — the `/health` endpoint is the only one that sees platform traffic.

This is the standard pattern for a self-hosted Telegram bot: portable, no AgentBase dependency, runs on any container host. It is, however, a poor fit for AgentBase — the container runs 24/7 regardless of traffic and the platform ecosystem (Memory, Identity, observability) is bypassed.

---

## AgentBase-Native Design — Webhook

Telegram pushes each message as a POST to the AgentBase endpoint. Every message becomes a traceable invocation.

| | Polling (current) | Webhook (target) |
| --- | --- | --- |
| Portability | Runs anywhere | Tied to AgentBase webhook URL |
| Scale-to-zero | No | Yes |
| In-memory state risk | Lost on restart | No — state in Memory Service |
| Cross-thread complexity | Yes | No |
| Parallel LLM calls | No | Yes (`asyncio.gather`) |
| Per-invocation observability | No | Yes |
| Local debugging | Easy | Requires ngrok |

---

## What You Gain After Migration

**Memory Service** — replaces `TTLCache`. Draft state survives restarts and works across replicas. Remove `cachetools` and `threading.Lock`.

**Observability** — each message has its own log stream, latency measurement, and CPU/RAM breakdown. Currently only container stdout is available.

**Identity Service** — store `AI_API_KEY` and `GOOGLE_SERVICE_ACCOUNT_JSON_BASE64` in AgentBase instead of env vars. Rotate without redeploying.

**Usage-based billing + scale-to-zero** — pay per message, not per hour. Set `--min-replicas 0`.

---

## Migration Phases

Must be done in order:

| Phase | Work | Time |
| --- | --- | --- |
| 1 — Externalize state | Migrate `_pending_drafts`, `_pending_resubmit`, `_partial_drafts` → Memory Service; `_chat_registry` → Google Sheets worksheet | ~5-6h |
| 2 — Switch to webhook | Disable polling, add `/telegram-webhook` route, register `setWebhook`, remove cross-thread bridges | ~3-4h |
| 3 — Async LLM | `httpx.AsyncClient`, `asyncio.gather` for classify + assist. Cuts LLM latency in half | ~2h |
| 4 — Identity Service | Remove secrets from env, fetch via `IdentityClient` at runtime | ~2h |

Phase 1+2 unlock the main benefits. Phase 3 is a latency improvement. Phase 4 is a security improvement and can be done independently after Phase 2.

Phase 1 is the prerequisite for everything else and carries the most risk — validate state persistence with polling still enabled before touching the network layer.

---

## When to Migrate

Migrate when you need any of:

- scale-to-zero (cost or idle time)
- per-message observability
- multi-replica support
- credential rotation without redeploying

Stay on polling if the bot is working well and the above are not priorities.
