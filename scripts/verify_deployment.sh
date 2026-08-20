#!/usr/bin/env bash
# Post-deploy smoke test against the LIVE Render + Vercel URLs -- run this
# after each of DEPLOYMENT_PLAN.md's deploy steps to confirm the deployed
# services actually work, not just that the dashboards say "Live".
#
# Usage:
#   BACKEND_URL=https://nameme-backend.onrender.com \
#   FRONTEND_URL=https://name-me.vercel.app \
#   ./scripts/verify_deployment.sh
#
# BACKEND_URL alone is enough to check the backend (e.g. right after step
# 1, before the frontend exists yet); add FRONTEND_URL once step 2 is done.

set -euo pipefail

: "${BACKEND_URL:?Set BACKEND_URL, e.g. https://nameme-backend.onrender.com}"
BACKEND_URL="${BACKEND_URL%/}"
FRONTEND_URL="${FRONTEND_URL:-}"
FRONTEND_URL="${FRONTEND_URL%/}"

# Render's free tier spins the service down after inactivity -- the first
# request after a while wakes it back up and can take 30-60s (see README's
# "Known trade-offs"). Poll instead of a single request with a short timeout.
echo "==> Waking up / checking $BACKEND_URL/api/health (up to 90s)"
health=""
for _ in $(seq 1 18); do
  if health=$(curl -sf -m 10 "$BACKEND_URL/api/health"); then
    break
  fi
  sleep 5
done
if [ -z "$health" ]; then
  echo "FAIL: backend never responded" >&2
  exit 1
fi
echo "$health"
echo "$health" | grep -q '"status":"ok"' || {
  echo "FAIL: health check did not report ok" >&2
  exit 1
}

echo
echo "==> POST $BACKEND_URL/api/search (real search, both models)"
for model in written_similarity cultural_similarity; do
  echo "--- model=$model"
  resp=$(curl -sS -m 30 -X POST "$BACKEND_URL/api/search" \
    -H "Content-Type: application/json" \
    -d "{\"liked_names\": [\"דוד\"], \"top_k\": 3, \"model\": \"$model\"}")
  echo "$resp"
  echo "$resp" | grep -q '"suggestions"' || {
    echo "FAIL: /api/search ($model) did not return suggestions" >&2
    exit 1
  }
done

echo
echo "==> CORS preflight from the frontend origin"
if [ -n "$FRONTEND_URL" ]; then
  cors=$(curl -sS -m 10 -o /dev/null -w "%{http_code}" -X OPTIONS "$BACKEND_URL/api/search" \
    -H "Origin: $FRONTEND_URL" \
    -H "Access-Control-Request-Method: POST")
  echo "OPTIONS status: $cors"
  [ "$cors" = "200" ] || {
    echo "FAIL: CORS preflight from $FRONTEND_URL was rejected -- check CORS_ORIGINS on Render" >&2
    exit 1
  }

  echo
  echo "==> GET $FRONTEND_URL (frontend actually serves the app shell)"
  frontend_html=$(curl -sS -m 15 "$FRONTEND_URL")
  echo "$frontend_html" | grep -qi "שם לי" || {
    echo "FAIL: frontend page did not contain the app's title text" >&2
    exit 1
  }
  echo "OK: frontend page loaded."
else
  echo "(skipped -- set FRONTEND_URL to also check CORS + the deployed frontend)"
fi

echo
echo "==> OK: deployment verified."
