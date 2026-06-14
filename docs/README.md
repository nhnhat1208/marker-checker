# Documentation Map

The docs are intentionally small and grouped into three areas.

## Product

- [Overview](./product-spec/overview.md)
- [Workflow And Lifecycle](./product-spec/workflow-and-lifecycle.md)
- [Data Model And Audit](./product-spec/data-model-and-audit.md)

## Technical

- [Architecture](./technical-design/architecture.md)
- [Configuration And Integrations](./technical-design/configuration-and-integrations.md)
- [Architecture Diagrams](./technical-design/architecture-diagrams.md) — C4 component + sequence diagrams for current (polling) and target (webhook) approaches
- [Standalone vs AgentBase-Native](./technical-design/standalone-vs-agentbase-native.md) — strategy overview: current design, why it's a poor fit for AgentBase, and what to gain by migrating

## Delivery

- [Implementation Plan](./delivery-plan/implementation-plan.md)
- [AgentBase Native Migration](./delivery-plan/agentbase-native-migration.md) — phased migration plan: session state → webhook → async LLM → Identity Service
