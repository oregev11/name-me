# syntax=docker/dockerfile:1
# ^ needed for `ADD --checksum` below (Dockerfile frontend >=1.5) -- BuildKit
# ignores this line if it isn't the very first line of the file, so don't
# move/remove it.

FROM python:3.12-slim AS base

RUN pip install --no-cache-dir uv

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

# cultural_similarity's quantized ONNX model (~112MB) is over GitHub's 100MB
# git blob limit, so it's hosted as a GitHub Release asset instead of being
# committed -- see DEPLOYMENT_PLAN.md and the root README's CI/CD section.
# `ADD` (not RUN curl) so BuildKit verifies the checksum itself and caches
# this layer keyed on the URL -- no extra `curl` package needed in the
# image, and a bad/corrupted download fails the build loudly instead of
# silently shipping a broken model file.
ADD --checksum=sha256:ab9754c56dc012929bebb839bbe79e276fbb8306ed212ffd00bf816914bb8b03 \
    https://github.com/oregev11/name-me/releases/download/cultural-similarity-onnx-v1/model_quantized.onnx \
    /app/src/nameme/artifacts/cultural_similarity/model_quantized.onnx

COPY README.md ./
RUN uv sync --frozen --no-dev

ENV PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Render (and most PaaS free tiers) inject $PORT; default to 8000 for local runs.
CMD ["sh", "-c", "uvicorn nameme.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
