import logging

from greennode_agentbase import GreenNodeAgentBaseApp, PingStatus, RequestContext
from starlette.requests import Request
from starlette.responses import JSONResponse

from agent.app import MarkerCheckerApp
from agent.persistence.postgres import PostgresWorkflowStore
from agent.web.server import setup_web_routes

logging.basicConfig(level=logging.INFO)
LOGGER = logging.getLogger(__name__)

app = GreenNodeAgentBaseApp()
runtime = MarkerCheckerApp()


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    return runtime.handle_invocation(payload=payload, context=context)


@app.ping
def health_check() -> PingStatus:
    return runtime.health_check()


async def _telegram_webhook(request: Request) -> JSONResponse:
    try:
        data = await request.json()
        runtime.handle_telegram_webhook(data)
    except Exception as exc:
        LOGGER.warning("telegram_webhook handler error: %s", exc)
    return JSONResponse({"ok": True})


app.add_route("/telegram-webhook", _telegram_webhook, methods=["POST"])

_pg_store = runtime._workflow_store if isinstance(runtime._workflow_store, PostgresWorkflowStore) else None
setup_web_routes(app, runtime._config, runtime._orchestrator, pg_store=_pg_store)


if __name__ == "__main__":
    runtime.start_background_services()
    app.run(port=8080, host="0.0.0.0")
