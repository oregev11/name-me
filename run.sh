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

# --- make sure uv/npm are actually resolvable ---
# `./run.sh` runs as a non-interactive shell, which does NOT source
# ~/.bashrc -- so tools installed via nvm (or anything else only wired up
# for interactive shells) can be invisible here even though they work fine
# in your normal terminal. Try loading nvm explicitly before giving up.
if ! command -v npm >/dev/null 2>&1; then
  export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
  if [ -s "$NVM_DIR/nvm.sh" ]; then
    # shellcheck disable=SC1091
    . "$NVM_DIR/nvm.sh"
  fi
fi

command -v uv >/dev/null 2>&1 || {
  echo "ERROR: 'uv' not found on PATH. Install: https://docs.astral.sh/uv/getting-started/installation/"
  exit 1
}
command -v npm >/dev/null 2>&1 || {
  echo "ERROR: 'npm' not found on PATH (tried loading nvm from \$NVM_DIR too)."
  echo "       Install Node.js, or if you use nvm, check that \$NVM_DIR is set correctly."
  exit 1
}

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

# wait_for <name> <url> <pid> <log_file> -- polls the URL, but also bails
# out immediately (with the log tail) if the background process has
# already died, instead of silently waiting out the full timeout.
wait_for() {
  local name="$1" url="$2" pid="$3" log="$4"
  echo -n "==> waiting for $name"
  for _ in $(seq 1 30); do
    if curl -sf "$url" >/dev/null 2>&1; then
      echo " ok"
      return 0
    fi
    if ! kill -0 "$pid" 2>/dev/null; then
      echo " FAILED (process exited early)"
      echo "----- last lines of $log -----"
      tail -20 "$log" || true
      echo "-------------------------------"
      return 1
    fi
    echo -n "."
    sleep 1
  done
  echo " FAILED (timed out)"
  echo "----- last lines of $log -----"
  tail -20 "$log" || true
  echo "-------------------------------"
  return 1
}

backend_ok=1
frontend_ok=1
wait_for "backend" "http://127.0.0.1:$BACKEND_PORT/api/health" "$BACKEND_PID" "$BACKEND_LOG" || backend_ok=0
wait_for "frontend" "http://127.0.0.1:$FRONTEND_PORT" "$FRONTEND_PID" "$FRONTEND_LOG" || frontend_ok=0

if [ "$backend_ok" -eq 0 ] || [ "$frontend_ok" -eq 0 ]; then
  echo ""
  echo "==> one or more services failed to start -- see logs above. Stopping."
  exit 1
fi

echo ""
echo "======================================================"
echo " name-me is running"
echo "   frontend:  http://127.0.0.1:$FRONTEND_PORT   <- open this one in your browser"
echo "   backend:   http://127.0.0.1:$BACKEND_PORT  (API only -- interactive docs at /docs)"
echo "   logs:      $LOG_DIR/"
echo " Press Ctrl+C to stop both."
echo "======================================================"

wait
