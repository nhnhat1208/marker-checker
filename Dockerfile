FROM python:3.11-slim

COPY --from=ghcr.io/astral-sh/uv:0.11.21 /uv /bin/

WORKDIR /app

# Install dependencies first (cached layer — only re-runs when pyproject.toml or uv.lock changes)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --compile-bytecode

# Copy source and install the project itself
COPY marker_checker_agent/ ./marker_checker_agent/
COPY main.py .
COPY runtime.yaml .
RUN uv sync --frozen --no-dev --compile-bytecode

# Pre-compile source files so the first request doesn't pay compilation cost
RUN uv run python -m compileall -q marker_checker_agent/ main.py

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

EXPOSE 8080

CMD ["/app/.venv/bin/python", "main.py"]
