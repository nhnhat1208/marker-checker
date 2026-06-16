from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from starlette.responses import FileResponse, HTMLResponse, Response
from starlette.staticfiles import StaticFiles

from agent.web.api import make_me_handler
from agent.web.auth import logout, make_callback_handler, make_login_handler
from agent.web.chat_ws import make_chat_ws_handler

if TYPE_CHECKING:
    from starlette.requests import Request

    from agent.config import RuntimeConfig
    from agent.persistence.postgres import PostgresWorkflowStore
    from agent.request_coordinator import RequestCoordinator

LOGGER = logging.getLogger(__name__)

_STATIC_DIR = Path("/app/static")


def setup_web_routes(
    app: object,
    config: RuntimeConfig,
    orchestrator: RequestCoordinator,
    pg_store: PostgresWorkflowStore | None = None,
) -> None:
    if not config.web.enabled:
        LOGGER.info("Web UI disabled (web.enabled: false)")
        return

    web_cfg = config.web

    # ── auth routes ──────────────────────────────────────────────────────────
    app.add_route("/auth/google", make_login_handler(web_cfg), methods=["GET"])  # type: ignore[attr-defined]
    app.add_route(
        "/auth/callback",
        make_callback_handler(web_cfg, pg_store),
        methods=["GET"],
    )  # type: ignore[attr-defined]
    app.add_route("/auth/logout", logout, methods=["GET"])  # type: ignore[attr-defined]

    # ── REST API ─────────────────────────────────────────────────────────────
    app.add_route("/api/me", make_me_handler(web_cfg), methods=["GET"])  # type: ignore[attr-defined]

    # ── WebSocket — must use router directly (GreenNodeAgentBaseApp has no add_websocket_route)
    app.router.add_websocket_route("/ws/chat", make_chat_ws_handler(web_cfg, orchestrator))  # type: ignore[attr-defined]

    # ── Static files + SPA fallback ──────────────────────────────────────────
    if _STATIC_DIR.exists():
        assets_dir = _STATIC_DIR / "assets"
        if assets_dir.exists():
            app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")  # type: ignore[attr-defined]
        app.add_route("/{path:path}", _make_spa_handler(_STATIC_DIR), methods=["GET"])  # type: ignore[attr-defined]
    else:
        LOGGER.warning(
            "Web UI static dir %s not found — React build missing. "
            "Run `pnpm run build` inside frontend/ or use Docker.",
            _STATIC_DIR,
        )
        app.add_route("/{path:path}", _spa_not_built, methods=["GET"])  # type: ignore[attr-defined]

    LOGGER.info("Web UI routes registered")


def _make_spa_handler(static_dir: Path):
    index_html = static_dir / "index.html"

    async def spa_fallback(request: Request) -> Response:
        path: str = request.path_params.get("path", "")
        # Don't intercept backend paths
        if path.startswith(("invocations", "health", "telegram-webhook", "api/", "auth/", "ws/")):
            return Response(status_code=404)
        # Serve static root files (favicon, manifest, robots.txt, etc.) directly
        candidate = (static_dir / path).resolve()
        if candidate.is_relative_to(static_dir.resolve()) and candidate.is_file():
            return FileResponse(str(candidate))
        if index_html.exists():
            return HTMLResponse(index_html.read_text(encoding="utf-8"))
        return Response("UI not built", status_code=404)

    return spa_fallback


async def _spa_not_built(request: Request) -> Response:
    path: str = request.path_params.get("path", "")
    if path.startswith(("invocations", "health", "telegram-webhook", "api/", "auth/", "ws/")):
        return Response(status_code=404)
    return HTMLResponse(
        "<html><body><h2>Web UI not built</h2>"
        "<p>Run <code>cd frontend && pnpm install && pnpm run build</code>, "
        "then copy <code>frontend/dist</code> to <code>/app/static</code>.</p></body></html>",
        status_code=503,
    )
