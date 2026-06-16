# Stage 1: Build React frontend
FROM node:22-slim AS frontend-builder
RUN npm install -g pnpm@10 --quiet
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/.npmrc ./
RUN pnpm install --frozen-lockfile
COPY frontend/ .
RUN pnpm run build

# Stage 2: Python runtime
FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/

WORKDIR /app

# Install dependencies first (cached layer — only re-runs when pyproject.toml or uv.lock changes)
COPY agent/pyproject.toml agent/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --compile-bytecode

# Copy source and install the project itself
COPY agent/src/agent/ ./agent/
COPY agent/main.py .
COPY runtime.yaml .
RUN uv sync --frozen --no-dev --compile-bytecode

# Copy built React UI
COPY --from=frontend-builder /frontend/dist /app/static

# Pre-compile source files so the first request doesn't pay compilation cost
RUN uv run python -m compileall -q agent/ main.py

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 8080

CMD ["/app/.venv/bin/python", "main.py"]
