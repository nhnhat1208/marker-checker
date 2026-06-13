from greennode_agentbase import GreenNodeAgentBaseApp, PingStatus, RequestContext

from marker_checker_agent.runtime import MarkerCheckerRuntime

app = GreenNodeAgentBaseApp()
runtime = MarkerCheckerRuntime()


@app.entrypoint
def handler(payload: dict, context: RequestContext) -> dict:
    return runtime.handle_invocation(payload=payload, context=context)


@app.ping
def health_check() -> PingStatus:
    return runtime.health_check()


if __name__ == "__main__":
    runtime.start_background_services()
    app.run(port=8080, host="0.0.0.0")
