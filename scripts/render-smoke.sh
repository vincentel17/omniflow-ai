#!/usr/bin/env bash
set -euo pipefail

API_BASE_URL="${API_BASE_URL:-}"
REDIS_URL="${REDIS_URL:-}"
WORKER_PING_TIMEOUT="${WORKER_PING_TIMEOUT:-10}"

if [[ -z "${API_BASE_URL}" ]]; then
  echo "API_BASE_URL is required"
  exit 1
fi

if [[ -z "${REDIS_URL}" ]]; then
  echo "REDIS_URL is required"
  exit 1
fi

echo "Checking API /health"
curl -fsS "${API_BASE_URL}/health" >/dev/null

echo "Checking API /ready"
curl -fsS "${API_BASE_URL}/ready" >/dev/null

echo "Checking basic API route /healthz"
curl -fsS "${API_BASE_URL}/healthz" >/dev/null

echo "Checking worker queue ping"
python - <<'PY'
import os
from celery import Celery

redis_url = os.environ["REDIS_URL"]
timeout_seconds = int(os.environ.get("WORKER_PING_TIMEOUT", "10"))
app = Celery("render-smoke", broker=redis_url, backend=redis_url)
result = app.send_task("worker.health.ping")
value = result.get(timeout=timeout_seconds)
if value != "pong":
    raise SystemExit(f"unexpected worker ping response: {value!r}")
print("worker ping ok")
PY

echo "Render smoke checks passed"
