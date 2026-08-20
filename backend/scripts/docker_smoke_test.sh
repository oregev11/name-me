#!/usr/bin/env bash
# Builds the backend's production Docker image and smoke-tests the actual
# container (not just the source code) before it ever reaches Render:
# builds -> runs -> hits /api/health and /api/search -> checks idle memory
# -> tears everything down. Safe to re-run any time; nothing it creates
# outlives the script.
#
# Usage (from repo root or backend/):
#   ./backend/scripts/docker_smoke_test.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
IMAGE="nameme-backend:smoke-test"
CONTAINER="nameme-backend-smoke-test"
PORT="${SMOKE_TEST_PORT:-18000}"

cleanup() {
  docker rm -f "$CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT

echo "==> Building $IMAGE from $BACKEND_DIR/Dockerfile"
docker build -t "$IMAGE" "$BACKEND_DIR"

echo "==> Starting container on port $PORT"
cleanup
docker run -d --name "$CONTAINER" -p "$PORT:8000" \
  -e CORS_ORIGINS=http://localhost:5173 \
  "$IMAGE" >/dev/null

echo "==> Waiting for the server to come up"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null; then
    break
  fi
  sleep 1
done

echo "==> GET /api/health"
health=$(curl -sS -m 10 "http://127.0.0.1:$PORT/api/health")
echo "$health"
echo "$health" | grep -q '"status":"ok"' || {
  echo "FAIL: health check did not report ok" >&2
  docker logs "$CONTAINER" >&2
  exit 1
}

echo "==> POST /api/search (sanity check: a real search returns real suggestions)"
search=$(curl -sS -m 15 -X POST "http://127.0.0.1:$PORT/api/search" \
  -H "Content-Type: application/json" \
  -d '{"liked_names": ["דוד"], "top_k": 3}')
echo "$search"
echo "$search" | grep -q '"suggestions"' || {
  echo "FAIL: /api/search did not return suggestions" >&2
  docker logs "$CONTAINER" >&2
  exit 1
}

echo "==> Idle memory usage (compare against README's ~250MB expectation)"
docker stats "$CONTAINER" --no-stream --format "{{.MemUsage}}"

echo "==> Image size"
docker images "$IMAGE" --format "{{.Size}}"

echo "==> OK: image builds, container starts, and serves real traffic."
