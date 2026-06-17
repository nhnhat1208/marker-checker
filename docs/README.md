# Documentation Guide

This repo keeps each topic in one place so the same explanation does not need to be repeated across files.

## Start Here

1. [Root README](../README.md) for getting started, commands, and project layout
2. [Product Overview](./product-spec/overview.md) for scope and boundaries
3. [Workflow Lifecycle](./product-spec/workflow-lifecycle.md) for request states and transitions
4. [Architecture](./technical-design/architecture.md) for backend structure
5. [Configuration, Integrations](./technical-design/configuration-integrations.md) for config and external services
6. [Web UI](./technical-design/web-ui.md) for the browser channel

## Product Docs

- [Overview](./product-spec/overview.md)
- [Workflow Lifecycle](./product-spec/workflow-lifecycle.md)
- [Data Model Audit](./product-spec/data-model-audit.md)

## Technical Docs

- [Architecture](./technical-design/architecture.md)
- [Configuration, Integrations](./technical-design/configuration-integrations.md)
- [Web UI](./technical-design/web-ui.md)
- [Architecture Diagrams](./technical-design/architecture-diagrams.md) — supplemental visual references; use the main architecture doc as the current source of truth

## Update Rules

- Update `README.md` when setup, commands, or top-level workflow changes.
- Update product docs when user-facing behavior changes.
- Update technical docs when implementation, routes, contracts, or integrations change.
- Keep `architecture-diagrams.md` aligned with `architecture.md`, but treat the main architecture doc as the source of truth.
