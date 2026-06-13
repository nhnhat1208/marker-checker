# System Diagrams

## C4 Level 1 — System Context

Who uses the system and what external systems does it depend on.

```mermaid
C4Context
    title System Context — Marker Checker Agent

    Person(requester, "Requester", "Submits change requests via Telegram or API")
    Person(approver, "Approver", "Reviews, approves, rejects, or asks for more info")
    Person(lookup_user, "Lookup User", "Queries request status and audit history")

    System(agent, "Marker Checker Agent", "Approval workflow agent — parses requests, manages lifecycle, records audit trail")

    System_Ext(telegram, "Telegram", "Messaging platform — delivers commands and freeform text")
    System_Ext(sheets, "Google Sheets", "Persists requests, audit events, and conversation links")
    System_Ext(llm, "LLM Provider", "OpenAI-compatible API — intent classification and request parsing (optional)")
    System_Ext(agentbase, "GreenNode AgentBase", "Runtime platform — HTTP endpoint, IAM, autoscaling, health checks")

    Rel(requester, telegram, "Sends requests and /confirm")
    Rel(approver, telegram, "Sends /approve /reject /needinfo /cancel")
    Rel(lookup_user, telegram, "Sends /status /history")
    Rel(telegram, agent, "Forwards messages via polling")
    Rel(agent, telegram, "Sends confirmations and notifications")
    Rel(agent, sheets, "Reads and writes requests, events, conversations")
    Rel(agent, llm, "POST /v1/chat/completions (optional, when ai.enabled=true)")
    Rel(agentbase, agent, "Routes POST /invocations, exposes health endpoint")
```

---

## C4 Level 2 — Container

The internal components running inside the single deployed container.

```mermaid
C4Container
    title Container — Marker Checker Agent

    Person(requester, "Requester / Approver")
    Person(api_caller, "API Caller", "Direct POST /invocations")

    System_Boundary(container, "Python Container on AgentBase") {
        Container(runtime, "MarkerCheckerRuntime", "Python", "Startup wiring: loads config, builds all components, starts Telegram polling")
        Container(telegram, "TelegramAdapter", "python-telegram-bot", "Polls Telegram, maps commands to orchestrator calls, sends replies")
        Container(orchestrator, "AgentOrchestrator", "Python", "Routes messages: regex → LLM → draft lifecycle → service dispatch")
        Container(intent_router, "FreeformIntentRouter", "Python / regex", "Regex patterns for lookup, cancel, history, resubmit, etc. in EN and VI")
        Container(ai, "RequestInputAssistant", "httpx", "classify_intent (80 tok) and assist_request_text (LLM parse). No-op when AI disabled.")
        Container(request_svc, "RequestService", "Python", "FSM lifecycle: create, approve, reject, needinfo, cancel, resubmit")
        Container(audit_svc, "AuditService", "Python", "Append-only audit events, timeline queries")
        ContainerDb(store, "GoogleSheetsWorkflowStore", "gspread", "Maps domain records to worksheet rows. Auto-creates worksheets on startup.")
    }

    System_Ext(telegram_ext, "Telegram Bot API")
    System_Ext(sheets_ext, "Google Sheets API")
    System_Ext(llm_ext, "LLM Provider (OpenAI-compatible)")

    Rel(requester, telegram, "Text messages and commands")
    Rel(api_caller, runtime, "POST /invocations JSON payload")
    Rel(telegram, telegram_ext, "Long-polling + sendMessage")
    Rel(telegram, orchestrator, "handle_requester_message / handle_approver_action")
    Rel(runtime, orchestrator, "handle_invocation dispatch")
    Rel(orchestrator, intent_router, "route(text) — fast path, no I/O")
    Rel(orchestrator, ai, "classify_intent / assist_request_text")
    Rel(orchestrator, request_svc, "create / approve / reject / cancel / resubmit")
    Rel(orchestrator, audit_svc, "record lookup events")
    Rel(request_svc, audit_svc, "record workflow events")
    Rel(request_svc, store, "CRUD request records")
    Rel(audit_svc, store, "append audit events")
    Rel(store, sheets_ext, "gspread read / append / update rows")
    Rel(ai, llm_ext, "POST /v1/chat/completions")
```

---

## C4 Level 3 — Request Handling Flow

How `AgentOrchestrator.handle_requester_message` routes a single incoming message.

```mermaid
flowchart TD
    IN([Message In]) --> CONFIRM{text == /confirm?}

    CONFIRM -- yes --> DRAFT_CHECK{pending draft\nexists?}
    DRAFT_CHECK -- no --> ERR_NO_DRAFT([error: no pending draft])
    DRAFT_CHECK -- yes --> CREATE[RequestService\ncreate_request]
    CREATE --> NOTIFY[notify approver]
    NOTIFY --> SUBMITTED([submitted])

    CONFIRM -- no --> REGEX_ROUTE[FreeformIntentRouter\nregex route]
    REGEX_ROUTE -- matched --> EXEC[_execute_routed_intent]
    EXEC --> DONE([response])

    REGEX_ROUTE -- no match --> PARSE[parse_request_text\nregex pattern]
    PARSE -- parsed --> FIELDS{missing\nrequired fields?}

    PARSE -- failed --> AI_ON{ai.enabled?}
    AI_ON -- no --> NEEDS_INPUT([needs_input: show usage hint])

    AI_ON -- yes --> CLASSIFY[classify_intent\nLLM — max 80 tok]
    CLASSIFY -- management op --> EXEC
    CLASSIFY -- confirm --> DRAFT_CHECK
    CLASSIFY -- new_request or unknown --> ASSIST[assist_request_text\nLLM — full parse]
    ASSIST -- parsed --> FIELDS
    ASSIST -- failed --> NEEDS_INPUT

    FIELDS -- yes --> CLARIFY[generate_clarification_message\nLLM optional]
    CLARIFY --> MISSING([missing_fields: ask for more info])

    FIELDS -- no --> STORE_DRAFT[store PendingDraft\nin memory, keyed by handle]
    STORE_DRAFT --> CONFIRM_REQ([confirmation_required: show summary])

    style SUBMITTED fill:#22c55e,color:#fff
    style DONE fill:#22c55e,color:#fff
    style MISSING fill:#f59e0b,color:#fff
    style CONFIRM_REQ fill:#3b82f6,color:#fff
    style NEEDS_INPUT fill:#ef4444,color:#fff
    style ERR_NO_DRAFT fill:#ef4444,color:#fff
```

---

## Approver Action Flow

How `handle_approver_action` processes an approve / reject / needinfo / cancel command.

```mermaid
flowchart LR
    IN([action + request_id + note]) --> DISPATCH{action}

    DISPATCH -- approve --> APPROVE[RequestService\napprove_request]
    DISPATCH -- reject --> REJECT[RequestService\nreject_request]
    DISPATCH -- needinfo --> NEEDINFO[RequestService\nrequest_more_info]
    DISPATCH -- cancel --> CANCEL[RequestService\ncancel_request]
    DISPATCH -- other --> ERR([error: unsupported action])

    APPROVE & REJECT & NEEDINFO & CANCEL --> AUDIT[AuditService\nrecord DECISION_RECORDED or NEEDS_INFO_REQUESTED]
    AUDIT --> SUMMARY[get_request_summary]
    SUMMARY --> MSG[generate_action_result_message\nLLM optional]
    MSG --> OK([ok + message + request payload])

    style OK fill:#22c55e,color:#fff
    style ERR fill:#ef4444,color:#fff
```

---

## Persistence Layer

How domain records map to Google Sheets worksheets.

```mermaid
erDiagram
    requests {
        string request_id PK
        string request_text
        string requester_handle
        string approver_handle
        string target_label
        string change_from_summary
        string change_to_summary
        string review_status
        int current_revision
        datetime created_at
        datetime updated_at
        datetime resolved_at
    }

    audit_events {
        string event_id PK
        string request_id FK
        int event_sequence
        string event_type
        string actor_handle
        string summary
        datetime occurred_at
    }

    request_conversations {
        string row_id PK
        string request_id FK
        string actor_handle
        string conversation_role
        string channel_id
        string thread_id
        datetime linked_at
    }

    requests ||--o{ audit_events : "has"
    requests ||--o{ request_conversations : "has"
```
