from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.config import RuntimeConfig

    from .base import WorkflowStore


def build_workflow_store(config: RuntimeConfig) -> WorkflowStore:
    backend = config.persistence.backend

    if backend == "postgres":
        from .postgres import PostgresWorkflowStore

        dsn = config.postgres.dsn.strip()
        if not dsn:
            raise ValueError(
                "persistence.backend is 'postgres' but POSTGRES_DSN is not set. "
                "Add POSTGRES_DSN to deploy.env."
            )
        return PostgresWorkflowStore(dsn)

    if backend == "google_sheets":
        from .google_sheets import GoogleSheetsWorkflowStore

        return GoogleSheetsWorkflowStore(config.google_sheets)

    raise ValueError(
        f"Unsupported persistence.backend: '{backend}'. "
        "Valid options: 'postgres', 'google_sheets'."
    )
