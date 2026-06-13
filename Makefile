VENV   := .venv
PYTHON := $(VENV)/bin/python
IMAGE  ?= marker-checker-agent:local

.PHONY: help install setup-config setup run run-no-telegram test health invoke-sample config-check ai-smoke docker-build

help:
	@printf "Requires uv (https://docs.astral.sh/uv/getting-started/installation/)\n"
	@printf "\n"
	@printf "Targets:\n"
	@printf "  make setup            Sync deps and create runtime.yaml if missing\n"
	@printf "  make run              Run the app locally\n"
	@printf "  make run-no-telegram  Run locally with Telegram polling disabled\n"
	@printf "  make test             Run unit tests\n"
	@printf "  make health           Check local health endpoint\n"
	@printf "  make invoke-sample    Send a sample local invocation\n"
	@printf "  make config-check     Validate config loading\n"
	@printf "  make ai-smoke         Run one real LLM input-assistance check\n"
	@printf "  make docker-build     Build local Docker image\n"

install:
	uv sync

setup-config:
	@if [ ! -f runtime.yaml ]; then cp runtime.example.yaml runtime.yaml; fi

setup: install setup-config

run:
	uv run python main.py

run-no-telegram:
	TELEGRAM_POLLING_ENABLED=false uv run python main.py

test:
	uv run pytest tests/ -v

health:
	curl -s -i http://127.0.0.1:8080/health

invoke-sample:
	curl -s -i -X POST http://127.0.0.1:8080/invocations \
		-H 'Content-Type: application/json' \
		-d '{"message":"for sample-object, change from disabled to enabled, ask @checker to approve","actor_name":"Requester One","actor_handle":"@requester"}'

config-check:
	uv run python -c "from marker_checker_agent.config import load_runtime_config; load_runtime_config(); print('Config OK')"

ai-smoke:
	bash -lc 'if [ -f .agentbase/deploy.env ]; then set -a; source .agentbase/deploy.env; set +a; fi; \
	uv run python -c "\
	from marker_checker_agent.config import load_runtime_config; \
	from marker_checker_agent.ai.assistant import build_input_assistant; \
	cfg = load_runtime_config(); \
	assistant = build_input_assistant(cfg.ai); \
	print({\"ai_enabled\": cfg.ai.enabled, \"model\": cfg.ai.model, \"base_url\": cfg.ai.base_url, \"assistant_built\": assistant is not None}); \
	result = assistant.assist_request_text(\"for sample-object, change from disabled to enabled, ask @checker to approve\"); \
	print({\"parser\": result.parser_name, \"guidance_message\": result.guidance_message}); \
	print(result.parsed_request)"'

docker-build:
	docker build -t $(IMAGE) .
