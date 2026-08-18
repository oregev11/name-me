#!/usr/bin/env bash
# Runs the whole name-me app locally: backend (FastAPI) + frontend (Vite).
#
# Usage:
#   ./run.sh              # start both, logs to .run-logs/, Ctrl+C stops both
#   BACKEND_PORT=8001 ./run.sh
#   FRONTEND_PORT=5174 ./run.sh
#   RELOAD=1 ./run.sh      # run the backend with --reload (for active dev)
#
# First run installs dependencies (uv sync / npm install) and creates .env
# files from .env.example if missing -- safe to re-run any time.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
LOG_DIR="$ROOT_DIR/.run-logs"
mkdir -p "$LOG_DIR"
BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"

echo "==> name-me: preparing local run"

# --- backend setup ---
cd "$BACKEND_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> created backend/.env from .env.example"
fi
if [ ! -d .venv ]; then
  echo "==> installing backend dependencies (uv sync)..."
  uv sync
fi

# --- frontend setup ---
cd "$FRONTEND_DIR"
if [ ! -f .env ]; then
  cp .env.example .env
  echo "==> created frontend/.env from .env.example"
fi
if [ ! -d node_modules ]; then
  echo "==> installing frontend dependencies (npm install)..."
  npm install
fi

# --- free up ports if a stale run is still holding them ---
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  pid=$(lsof -ti:"$port" -sTCP:LISTEN 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo "==> port $port already in use (pid $pid) -- stopping it"
    kill "$pid" 2>/dev/null || true
    sleep 1
  fi
done

# --- start backend ---
cd "$BACKEND_DIR"
UVICORN_ARGS=(uvicorn nameme.main:app --host 127.0.0.1 --port "$BACKEND_PORT")
[ "${RELOAD:-0}" = "1" ] && UVICORN_ARGS+=(--reload)
echo "==> starting backend on http://127.0.0.1:$BACKEND_PORT (log: $BACKEND_LOG)"
uv run "${UVICORN_ARGS[@]}" >"$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!

# --- start frontend ---
cd "$FRONTEND_DIR"
echo "==> starting frontend on http://127.0.0.1:$FRONTEND_PORT (log: $FRONTEND_LOG)"
npm run dev -- --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

cleanup() {
  echo ""
  echo "==> stopping servers..."
  # `npm run dev`'s PID is just the npm wrapper -- npm does not forward
  # signals to the actual vite server it spawns, so $FRONTEND_PID alone
  # won't stop it. Kill by port for both, which works regardless.
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  lsof -ti:"$BACKEND_PORT" -sTCP:LISTEN 2>/dev/null | xargs -r kill 2>/dev/null || true
  lsof -ti:"$FRONTEND_PORT" -sTCP:LISTEN 2>/dev/null | xargs -r kill 2>/dev/null || true
  wait "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
  echo "==> stopped"
}
trap cleanup EXIT INT TERM

echo -n "==> waiting for backend"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$BACKEND_PORT/api/health" >/dev/null 2>&1; then
    echo " ok"
    break
  fi
  echo -n "."
  sleep 1
done

echo -n "==> waiting for frontend"
for _ in $(seq 1 30); do
  if curl -sf "http://127.0.0.1:$FRONTEND_PORT" >/dev/null 2>&1; then
    echo " ok"
    break
  fi
  echo -n "."
  sleep 1
done

echo ""
echo "======================================================"
echo " name-me is running"
echo "   frontend:  http://127.0.0.1:$FRONTEND_PORT"
echo "   backend:   http://127.0.0.1:$BACKEND_PORT  (interactive docs at /docs)"
echo "   logs:      $LOG_DIR/"
echo " Press Ctrl+C to stop both."
echo "======================================================"

wait
