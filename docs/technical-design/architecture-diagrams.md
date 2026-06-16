# Architecture Diagrams

Current architecture uses webhook mode in production. Polling mode is available as a local
development fallback (`TELEGRAM_MODE=polling` via `runtime.local.yaml` or env var).

---

## Current Architecture — Webhook

### Component Overview

```mermaid
graph TB
    subgraph ext["External Systems"]
        TG["Telegram API"]
        GS["Google Sheets API"]
        LLM["LLM Provider\n(httpx.Client)"]
        MEM["AgentBase\nMemory Service\n(user prefs / approver patterns)"]
    end

    subgraph container["Container"]
        subgraph main["main.py"]
            AB["GreenNodeAgentBaseApp\n/invoke  /health\n/telegram-webhook"]
        end

        subgraph runtime["MarkerCheckerRuntime"]
            ORCH["RequestCoordinator"]
            DM["DraftManager\n\n_pending_drafts TTLCache → GS\n_pending_resubmit TTLCache → GS\n_partial_drafts TTLCache (in-memory only)\n_chat_registry LRUCache → GS"]
            RS["RequestService\nAuditService"]
            AI["RequestInputAssistant"]
            AMEM["AgentMemoryService"]
        end

        subgraph adapter["TelegramAdapter"]
            WHK["_webhook_thread\n(daemon thread)"]
            LOOP["asyncio event loop\n(inside _webhook_thread)"]
            PTB["PTB Application\ncommand + message handlers"]
        end
    end

    AB -->|"POST /telegram-webhook\npushed by Telegram"| LOOP
    AB -->|"handle_invocation()\nsync call"| ORCH
    LOOP --> PTB
    PTB -->|"asyncio.to_thread()"| ORCH
    ORCH --> DM
    DM -->|"fire-and-forget writes"| GS
    ORCH --> RS
    RS -->|"gspread sync"| GS
    ORCH --> AI
    AI -->|"httpx.Client\nThreadPoolExecutor"| LLM
    ORCH --> AMEM
    AMEM -->|"HTTP"| MEM
    PTB -->|"send_message\nasyncio.run_coroutine_threadsafe"| TG
    WHK -->|"owns"| LOOP
    TG -->|"pushes updates"| AB
```

### Request Path — Requester sends a message (webhook)

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant AB as AgentBase Runtime<br/>/telegram-webhook
    participant ADPT as TelegramAdapter<br/>webhook loop
    participant TP as Thread Pool<br/>(asyncio.to_thread)
    participant ORCH as Orchestrator
    participant LLM as LLM Provider
    participant GS as Google Sheets

    U->>TGAPI: sends message
    TGAPI->>AB: POST /telegram-webhook {update}
    Note over TGAPI,AB: Telegram pushes — no polling
    AB->>ADPT: asyncio.run_coroutine_threadsafe(process_update)
    ADPT->>ADPT: PTB parses Update, dispatches to _text_message
    ADPT->>TP: asyncio.to_thread(orchestrator.handle_requester_message)
    Note over ADPT,TP: Webhook loop freed while orchestrator runs
    TP->>ORCH: handle_requester_message(text, handle)
    ORCH->>ORCH: draft_manager.pop_resubmit(handle)
    par classify + assist in parallel (ThreadPoolExecutor)
        ORCH->>LLM: classify_intent(text) [httpx sync]
        ORCH->>LLM: assist_request_text(text) [httpx sync]
    end
    LLM-->>ORCH: IntentNewRequest + AssistedParseResult
    ORCH->>ORCH: draft_manager.set_draft(handle, draft)
    Note over ORCH,GS: fire-and-forget write to GS in background thread
    ORCH-->>TP: {status: CONFIRMATION_REQUIRED, message: ...}
    TP-->>ADPT: result dict
    ADPT->>TGAPI: asyncio.run_coroutine_threadsafe(bot.send_message)
    TGAPI-->>U: "Here is your draft..."
    AB-->>TGAPI: {"ok": true}
```

### Request Path — /confirm → submit → notify approver (webhook)

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant AB as AgentBase Runtime
    participant ADPT as TelegramAdapter
    participant TP as Thread Pool
    participant ORCH as Orchestrator
    participant GS as Google Sheets
    participant APRVR as Approver (Telegram)

    U->>TGAPI: /confirm
    TGAPI->>AB: POST /telegram-webhook {update}
    AB->>ADPT: asyncio.run_coroutine_threadsafe(process_update)
    ADPT->>TP: asyncio.to_thread(orchestrator.handle_requester_message, "/confirm")
    TP->>ORCH: handle_requester_message("/confirm")
    ORCH->>ORCH: draft_manager.pop_draft(handle)
    Note over ORCH,GS: draft loaded from TTLCache or GS fallback
    ORCH->>GS: request_service.create_request() [gspread sync]
    GS-->>ORCH: RequestRecord
    ORCH->>ORCH: notifier.notify_approver(payload)
    Note over ORCH: Still in thread pool worker —<br/>cannot await bot.send_message directly
    ORCH->>ADPT: asyncio.run_coroutine_threadsafe(bot.send_message, loop)
    Note over ORCH,ADPT: Cross-thread bridge into webhook event loop
    ADPT->>TGAPI: send_message to approver chat_id
    TGAPI-->>APRVR: "📋 New approval request..."
    ORCH-->>TP: {status: SUBMITTED}
    TP-->>ADPT: result dict
    ADPT->>TGAPI: asyncio.run_coroutine_threadsafe(bot.send_message)
    TGAPI-->>U: "Request REQ-XXXX submitted"
    AB-->>TGAPI: {"ok": true}
```

---

## Polling Mode — Local Development Fallback

Set `telegram.mode: polling` in `runtime.local.yaml` (or `TELEGRAM_MODE=polling` env var). No `GREENNODE_ENDPOINT_URL` required.

### Component Overview (Polling)

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
            DM["DraftManager\n\n_pending_drafts TTLCache → GS\n_pending_resubmit TTLCache → GS\n_partial_drafts TTLCache (in-memory only)\n_chat_registry LRUCache → GS"]
            RS["RequestService\nAuditService"]
            AI["RequestInputAssistant"]
        end

        subgraph adapter["TelegramAdapter"]
            PT["polling_thread\n(daemon thread)"]
            LOOP["asyncio event loop\n(inside polling_thread)"]
            PTB["PTB Application\ncommand + message handlers"]
        end
    end

    AB -->|"handle_invocation()\nsync call"| ORCH
    ORCH -->|"callback via\nasyncio.run_coroutine_threadsafe"| LOOP
    LOOP --> PTB
    PTB -->|"asyncio.to_thread()"| ORCH
    ORCH --> DM
    DM -->|"fire-and-forget writes"| GS
    ORCH --> RS
    RS -->|"gspread sync"| GS
    ORCH --> AI
    AI -->|"httpx.Client\nThreadPoolExecutor"| LLM
    PT -->|"owns"| LOOP
    LOOP -->|"getUpdates polling"| TG
    PTB -->|"send_message"| TG
```

### Request Path — Requester sends a message (polling)

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant PTHR as Polling Loop<br/>(daemon thread)
    participant TP as Thread Pool<br/>(asyncio.to_thread)
    participant ORCH as Orchestrator
    participant LLM as LLM Provider
    participant GS as Google Sheets

    PTHR->>TGAPI: GET getUpdates (every second)
    TGAPI-->>PTHR: [update: text message]
    PTHR->>PTHR: dispatch to _text_message handler (async)
    PTHR->>TP: asyncio.to_thread(orchestrator.handle_requester_message)
    Note over PTHR,TP: Polling loop is freed while orchestrator runs
    TP->>ORCH: handle_requester_message(text, handle)
    ORCH->>ORCH: draft_manager.pop_resubmit(handle)
    par classify + assist in parallel (ThreadPoolExecutor)
        ORCH->>LLM: classify_intent(text) [httpx sync]
        ORCH->>LLM: assist_request_text(text) [httpx sync]
    end
    LLM-->>ORCH: IntentNewRequest + AssistedParseResult
    ORCH->>ORCH: draft_manager.set_draft(handle, draft)
    Note over ORCH,GS: fire-and-forget write to GS in background thread
    ORCH-->>TP: {status: CONFIRMATION_REQUIRED, message: ...}
    TP-->>PTHR: result dict
    PTHR->>TGAPI: reply_text("Here is your draft...")
    TGAPI-->>U: message
```

### Request Path — /confirm → submit → notify approver (polling)

```mermaid
sequenceDiagram
    participant U as User (Telegram)
    participant TGAPI as Telegram API
    participant PTHR as Polling Loop<br/>(daemon thread)
    participant TP as Thread Pool
    participant ORCH as Orchestrator
    participant GS as Google Sheets
    participant APRVR as Approver (Telegram)

    U->>TGAPI: /confirm
    TGAPI-->>PTHR: update
    PTHR->>TP: asyncio.to_thread(orchestrator.handle_requester_message, "/confirm")
    TP->>ORCH: handle_requester_message("/confirm")
    ORCH->>ORCH: draft_manager.pop_draft(handle)
    ORCH->>GS: create_request() [gspread sync]
    GS-->>ORCH: RequestRecord
    ORCH->>ORCH: notifier.notify_approver(payload)
    Note over ORCH: Still in thread pool worker —<br/>cannot await bot.send_message directly
    ORCH->>PTHR: asyncio.run_coroutine_threadsafe(bot.send_message, loop)
    Note over ORCH,PTHR: Cross-thread bridge back into polling loop
    PTHR->>TGAPI: send_message to approver chat_id
    TGAPI-->>APRVR: "📋 New approval request..."
    ORCH-->>TP: {status: SUBMITTED}
    TP-->>PTHR: result dict
    PTHR->>TGAPI: reply_text("Request REQ-XXXX submitted")
    TGAPI-->>U: message
```
