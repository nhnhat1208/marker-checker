# Architecture Diagrams

Two approaches side by side: current (polling) and target (webhook + AgentBase-native).

---

## Current Architecture — Polling

### Component Overview

```mermaid
graph TB
    subgraph ext["External Systems"]
        TG["Telegram API"]
        GS["Google Sheets API"]
        LLM["LLM Provider\n(httpx.Client)"]
    end

    subgraph container["Container — runs 24/7"]
        subgraph main["main.py"]
            AB["GreenNodeAgentBaseApp\n/invoke  /health"]
        end

        subgraph runtime["MarkerCheckerRuntime"]
            ORCH["RequestCoordinator"]
            DM["DraftManager\n\n_pending_drafts TTLCache\n_pending_resubmit TTLCache\n_partial_drafts TTLCache\n_lock (threading.Lock)"]
            RS["RequestService\nAuditService"]
            AI["RequestInputAssistant"]
        end

        subgraph adapter["TelegramAdapter"]
            PT["polling_thread\n(daemon thread)"]
            LOOP["asyncio event loop\n(inside polling_thread)"]
            PTB["PTB Application\ncommand + message handlers"]
        end

        CACHE["LRUCache\n_chat_registry"]
    end

    AB -->|"handle_invocation()\nsync call"| ORCH
    ORCH -->|"callback via\nasyncio.run_coroutine_threadsafe"| LOOP
    LOOP --> PTB
    PTB -->|"asyncio.to_thread()"| ORCH
    ORCH --> DM
    ORCH --> RS
    RS -->|"gspread sync"| GS
    ORCH --> AI
    AI -->|"httpx.Client\nsync"| LLM
    PTB --> CACHE
    PT -->|"owns"| LOOP
    LOOP -->|"getUpdates polling"| TG
    PTB -->|"send_message"| TG
```

### Request Path — Requester sends a message

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant LOOP as Polling Loop<br/>(daemon thread)
    participant TP as Thread Pool<br/>(asyncio.to_thread)
    participant ORCH as Orchestrator
    participant LLM as LLM Provider
    participant GS as Google Sheets

    LOOP->>TGAPI: GET getUpdates (every second)
    TGAPI-->>LOOP: [update: text message]
    LOOP->>LOOP: dispatch to _text_message handler (async)
    LOOP->>TP: asyncio.to_thread(orchestrator.handle_requester_message)
    Note over LOOP,TP: Polling loop is freed while orchestrator runs
    TP->>ORCH: handle_requester_message(text, handle)
    ORCH->>ORCH: draft_manager.pop_resubmit(handle)
    ORCH->>LLM: classify_intent(text) [httpx sync]
    LLM-->>ORCH: IntentNewRequest
    ORCH->>LLM: assist_request_text(text) [httpx sync]
    LLM-->>ORCH: AssistedParseResult
    ORCH->>ORCH: draft_manager.set_draft(handle, draft)
    ORCH-->>TP: {status: CONFIRMATION_REQUIRED, message: ...}
    TP-->>LOOP: result dict
    LOOP->>TGAPI: reply_text("Here is your draft...")
    TGAPI-->>U: message
```

### Request Path — /confirm → submit → notify approver

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant LOOP as Polling Loop<br/>(daemon thread)
    participant TP as Thread Pool
    participant ORCH as Orchestrator
    participant GS as Google Sheets
    participant APRVR as Approver (Telegram)

    U->>TGAPI: /confirm
    TGAPI-->>LOOP: update
    LOOP->>TP: asyncio.to_thread(orchestrator.handle_requester_message, "/confirm")
    TP->>ORCH: handle_requester_message("/confirm")
    ORCH->>ORCH: draft_manager.pop_draft(handle)
    ORCH->>GS: create_request() [gspread sync]
    GS-->>ORCH: RequestRecord
    ORCH->>ORCH: notifier.notify_approver(payload)
    Note over ORCH: Still in thread pool worker —<br/>cannot await bot.send_message directly
    ORCH->>LOOP: asyncio.run_coroutine_threadsafe(bot.send_message, loop)
    Note over ORCH,LOOP: Cross-thread bridge back into polling loop
    LOOP->>TGAPI: send_message to approver chat_id
    TGAPI-->>APRVR: "📋 New approval request..."
    ORCH-->>TP: {status: SUBMITTED}
    TP-->>LOOP: result dict
    LOOP->>TGAPI: reply_text("Request REQ-XXXX submitted")
    TGAPI-->>U: message
```

---

## Target Architecture — Webhook + AgentBase-Native

### Component Overview

```mermaid
graph TB
    subgraph ext["External Systems"]
        TG["Telegram API"]
        GS["Google Sheets API"]
        LLM["LLM Provider\n(httpx.AsyncClient)"]
        MEM["AgentBase\nMemory Service"]
    end

    subgraph container["Container — scales to zero"]
        subgraph main["main.py"]
            AB["GreenNodeAgentBaseApp\n/invoke  /health\n/telegram-webhook  ← new"]
        end

        subgraph runtime["MarkerCheckerRuntime"]
            ORCH["RequestCoordinator\n\n(no in-memory state)\n(no locks)"]
            RS["RequestService\nAuditService"]
            AI["RequestInputAssistant"]
            MC["MemoryClient"]
        end

        subgraph adapter["TelegramAdapter"]
            PU["process_update()\nasync"]
            PTB["PTB Application\ncommand + message handlers"]
        end
    end

    AB -->|"POST /telegram-webhook\npushed by Telegram"| PU
    AB -->|"handle_invocation()\nsync call"| ORCH
    PU --> PTB
    PTB -->|"await orchestrator methods"| ORCH
    ORCH -->|"await memory_client"| MC
    MC -->|"HTTP"| MEM
    ORCH --> RS
    RS -->|"gspread"| GS
    ORCH --> AI
    AI -->|"httpx.AsyncClient\nawait"| LLM
    ORCH -->|"await notify_approver()\ndirect, no thread bridge"| TG
    TG -->|"pushes updates"| AB
```

### Request Path — Requester sends a message (webhook)

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant AB as AgentBase Runtime<br/>/telegram-webhook
    participant ADPT as TelegramAdapter<br/>process_update()
    participant ORCH as Orchestrator<br/>(async)
    participant MEM as Memory Service
    participant LLM as LLM Provider
    participant GS as Google Sheets

    U->>TGAPI: sends message
    TGAPI->>AB: POST /telegram-webhook {update}
    Note over TGAPI,AB: Telegram pushes — no polling
    AB->>ADPT: await telegram_adapter.process_update(data)
    ADPT->>ADPT: PTB parses Update, dispatches to _text_message
    ADPT->>ORCH: await orchestrator.handle_requester_message()
    ORCH->>MEM: await memory_client.get("pending_draft:{handle}")
    MEM-->>ORCH: null
    ORCH->>LLM: await classify_intent(text)
    LLM-->>ORCH: IntentNewRequest
    ORCH->>LLM: await asyncio.gather(classify, assist)
    Note over ORCH,LLM: Two LLM calls run concurrently
    LLM-->>ORCH: results
    ORCH->>MEM: await memory_client.set("pending_draft:{handle}", json)
    MEM-->>ORCH: ok
    ORCH-->>ADPT: {status: CONFIRMATION_REQUIRED}
    ADPT->>TGAPI: await reply_text("Here is your draft...")
    TGAPI-->>U: message
    AB-->>TGAPI: {"ok": true}
```

### Request Path — /confirm → submit → notify approver (webhook)

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant AB as AgentBase Runtime
    participant ADPT as TelegramAdapter
    participant ORCH as Orchestrator
    participant MEM as Memory Service
    participant GS as Google Sheets
    participant APRVR as Approver (Telegram)

    U->>TGAPI: /confirm
    TGAPI->>AB: POST /telegram-webhook {update}
    AB->>ADPT: await process_update(data)
    ADPT->>ORCH: await orchestrator.handle_requester_message("/confirm")
    ORCH->>MEM: await memory_client.get("pending_draft:{handle}")
    MEM-->>ORCH: PendingDraft JSON
    ORCH->>ORCH: deserialize draft
    ORCH->>GS: await request_service.create_request()
    GS-->>ORCH: RequestRecord
    ORCH->>ORCH: await _notify_approver(payload)
    Note over ORCH: _notify_approver is now async —<br/>no thread bridge needed
    ORCH->>TGAPI: await bot.send_message(approver_chat_id, text)
    TGAPI-->>APRVR: "📋 New approval request..."
    ORCH-->>ADPT: {status: SUBMITTED}
    ADPT->>TGAPI: await reply_text("Request REQ-XXXX submitted")
    TGAPI-->>U: message
    AB-->>TGAPI: {"ok": true}
```

---

## Key Differences

| | Current (Polling) | Target (Webhook) |
|---|---|---|
| Thread model | 2 threads: main + polling daemon | 1 async event loop |
| Telegram receive | daemon thread polls every ~1s | Telegram pushes POST per message |
| State storage | in-process TTLCache | AgentBase Memory Service |
| Notification path | `asyncio.run_coroutine_threadsafe` cross-thread | direct `await bot.send_message` |
| LLM calls | sync `httpx.Client`, sequential | `httpx.AsyncClient`, `asyncio.gather` concurrent |
| AgentBase billing | container idle 24/7 | per-invocation |
| Observability | container stdout only | per-invocation logs + latency |
| Startup | always running | scale-to-zero, cold start ~2s |
