FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Render (and most PaaS free tiers) inject $PORT; default to 8000 for local runs.
CMD ["sh", "-c", "uvicorn nameme.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
