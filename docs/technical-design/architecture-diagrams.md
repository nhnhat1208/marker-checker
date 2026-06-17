# Architecture Diagrams

Supplementary diagrams for the current implementation. The primary narrative stays in [Architecture](./architecture.md); this file exists for readers who want visual flow references.

## Current Runtime

```mermaid
flowchart TB
    TG[Telegram]
    API[API Invocation]
    WEB[Browser Web UI]

    subgraph runtime[Agent Runtime]
        MAIN[main.py / AgentBase app]
        TA[TelegramAdapter]
        WS[Web routes + ChatWsHandler]
        ORCH[RequestCoordinator]
        DRAFTS[DraftManager]
        QRY[RequestQueryService]
        REQ[RequestService]
        AUDIT[AuditService]
        AI[RequestInputAssistant]
        MEM[AgentMemoryService]
    end

    subgraph storage[Persistence]
        PG[(Postgres default)]
        GS[(Google Sheets fallback)]
    end

    TG --> MAIN
    API --> MAIN
    WEB --> WS
    MAIN --> TA
    MAIN --> ORCH
    TA --> ORCH
    WS --> ORCH
    ORCH --> DRAFTS
    ORCH --> QRY
    ORCH --> REQ
    ORCH --> AUDIT
    ORCH -. optional .-> AI
    ORCH -. optional .-> MEM
    DRAFTS --> PG
    DRAFTS -. fallback .-> GS
    QRY --> PG
    QRY -. fallback .-> GS
    REQ --> PG
    REQ -. fallback .-> GS
    AUDIT --> PG
    AUDIT -. fallback .-> GS
```

## Requester Message Path

```mermaid
sequenceDiagram
    participant U as User
    participant C as Channel
    participant O as RequestCoordinator
    participant R as FreeformIntentRouter
    participant D as DraftManager
    participant A as RequestInputAssistant
    participant S as RequestService
    participant P as Persistence

    U->>C: Send message
    C->>O: handle_requester_message(...)
    O->>O: confirm/discard fast-path?
    O->>R: route(text)
    alt management/query intent matched
        R-->>O: RoutedIntent
        O->>O: execute routed operation
    else new request flow
        O->>O: regex request parsing
        alt parsed directly
            O->>D: set draft
            O-->>C: confirmation_required
        else needs contextual or AI help
            O->>D: pop resubmit?
            alt resubmission pending
                O->>S: resubmit_request(...)
                S->>P: persist revision
                O-->>C: ok
            else AI fallback
                O->>A: classify + assist
                alt enough fields
                    O->>D: set draft
                    O-->>C: confirmation_required
                else missing fields
                    O-->>C: missing_fields
                end
            end
        end
    end
```

## Web Channel

```mermaid
sequenceDiagram
    participant B as Browser
    participant W as Web Routes
    participant S as Session/Auth
    participant H as ChatWsHandler
    participant O as RequestCoordinator

    B->>W: GET /auth/google
    W-->>B: Redirect to Google
    B->>W: GET /auth/callback
    W->>S: set signed cookie
    W-->>B: Redirect /
    B->>W: WS /ws/chat
    W->>S: validate cookie
    W->>H: create authenticated handler
    B->>H: message | structured_message | action
    H->>O: dispatch typed request
    O-->>H: response + optional ui_response
    H-->>B: done
```

## Contract Generation

```mermaid
flowchart LR
    PY[agent/src/agent/contracts/ws.py]
    AA[contracts/asyncapi.yaml]
    TS[frontend/src/lib/generated/ws-contract.ts]

    PY -->|make contracts| AA
    AA -->|node frontend/scripts/gen-contracts.mjs| TS
```
