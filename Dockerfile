FROM python:3.11-slim

# uv: fast dependency resolver + installer (~10x faster than pip)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

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

EXPOSE 8080

CMD ["uv", "run", "python", "main.py"]
