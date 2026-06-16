# ── Deployment config — set in deploy.env (copy from deploy.example.env) ──────
-include deploy.env

IMAGE_REPO ?=
RUNTIME_ID ?=
FLAVOR     ?=

ifeq ($(origin TAG), undefined)
TAG := v$(shell date +%Y%m%d%H%M%S)
endif
IMG := $(IMAGE_REPO):$(TAG)

SCRIPTS := .claude/skills/agentbase/scripts

_require-env:
	@[ -f deploy.env ] || { echo "ERROR: deploy.env not found — copy deploy.example.env and fill in values"; exit 1; }

_require-deploy-env: _require-env
	@[ -n "$(IMAGE_REPO)" ] || { echo "ERROR: IMAGE_REPO is not set in deploy.env"; exit 1; }
	@[ -n "$(RUNTIME_ID)" ] || { echo "ERROR: RUNTIME_ID is not set in deploy.env"; exit 1; }
	@[ -n "$(FLAVOR)" ]     || { echo "ERROR: FLAVOR is not set in deploy.env"; exit 1; }

.PHONY: help install run frontend test contracts config-check smoke health invoke-sample \
        docker-build docker-push deploy logs _require-env _require-deploy-env

help:
	@printf "Usage: make <target>\n\n"
	@printf "Local dev:\n"
	@printf "  make install       Sync Python dependencies (uv)\n"
	@printf "  make run           Run agent locally (port 8080, loads deploy.env)\n"
	@printf "  make frontend      Run frontend dev server (port 3000, rsbuild)\n"
	@printf "  make test          Run unit tests\n"
	@printf "  make contracts     Regenerate AsyncAPI spec + TypeScript types\n"
	@printf "  make config-check  Validate config loads without errors\n"
	@printf "  make smoke         Run Postgres smoke test\n"
	@printf "  make health        Ping local health endpoint (port 8080)\n"
	@printf "  make invoke-sample Send a sample invocation to local server\n"
	@printf "\n"
	@printf "Deploy (requires deploy.env):\n"
	@printf "  make docker-build  Build linux/amd64 image (TAG=vYYYYMMDDHHMMSS)\n"
	@printf "  make docker-push   Push image to AgentBase CR\n"
	@printf "  make deploy        Build + push + update runtime (one command)\n"
	@printf "  make logs          Fetch latest 200 runtime log lines\n"

# ── Local dev ────────────────────────────────────────────────────────────────

install:
	uv --project agent sync

run: _require-env
	@set -a; . ./deploy.env; set +a; \
	GOOGLE_REDIRECT_URI=http://localhost:3000/auth/callback \
	uv --project agent run python agent/main.py

frontend:
	cd frontend && pnpm run dev

test:
	uv --project agent run pytest tests/ -v

contracts:
	uv --project agent run python agent/scripts/gen_asyncapi.py
	node frontend/scripts/gen-contracts.mjs

config-check: _require-env
	@set -a; . ./deploy.env; set +a; \
	uv --project agent run python -c "from agent.config import load_runtime_config; load_runtime_config(); print('Config OK')"

smoke: _require-env
	@set -a; . ./deploy.env; set +a; \
	uv --project agent run python -c "\
import os; \
from agent.persistence.postgres import PostgresWorkflowStore; \
store = PostgresWorkflowStore(os.environ['POSTGRES_DSN']); \
store.initialize(); \
print('Schema OK'); \
print('Chat registry:', store.load_chat_registry()); \
print('Smoke PASSED')"

health:
	curl -s -i http://127.0.0.1:8080/health

invoke-sample:
	curl -s -i -X POST http://127.0.0.1:8080/invocations \
		-H 'Content-Type: application/json' \
		-d '{"message":"for sample-object, change from disabled to enabled, ask @checker to approve","actor_name":"Requester One","actor_handle":"@requester"}'

# ── Deploy ───────────────────────────────────────────────────────────────────

docker-build: _require-deploy-env
	docker build --platform linux/amd64 -t $(IMG) .
	@echo "Built: $(IMG)"

docker-push: _require-deploy-env
	bash $(SCRIPTS)/cr.sh credentials docker-login
	docker push $(IMG)
	@echo "Pushed: $(IMG)"

deploy: docker-build docker-push
	bash $(SCRIPTS)/runtime.sh update $(RUNTIME_ID) \
		--image $(IMG) \
		--flavor $(FLAVOR) \
		--from-cr \
		--env-file deploy.env \
		--min-replicas 1 --max-replicas 1 \
		--cpu-scale 50 --mem-scale 50
	@echo "Deployed: $(IMG)"

logs: _require-deploy-env
	bash $(SCRIPTS)/runtime.sh logs $(RUNTIME_ID) --from 0 --limit 200
