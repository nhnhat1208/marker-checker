from __future__ import annotations

from typing import TYPE_CHECKING

from marker_checker_agent.config import RuntimeConfig

from .base import WorkflowStore

if TYPE_CHECKING:
    from .google_sheets import GoogleSheetsWorkflowStore


def build_workflow_store(config: RuntimeConfig) -> WorkflowStore:
    if config.app.persistence_backend != "google_sheets":
        raise ValueError(
            "Unsupported persistence backend: "
            f"{config.app.persistence_backend}. Only google_sheets is configured."
        )

    from .google_sheets import GoogleSheetsWorkflowStore

    return GoogleSheetsWorkflowStore(config.google_sheets)
