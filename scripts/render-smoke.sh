#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${BASE_URL:-}"
if [[ -z "${BASE_URL}" ]]; then
  echo "BASE_URL is required, for example BASE_URL=https://omniflow-api-staging.onrender.com"
  exit 1
fi

SMOKE_USER_ID="${OMNIFLOW_SMOKE_USER_ID:-7e03f43e-9e88-5d95-bb87-1780a0a618a2}"
SMOKE_ORG_ID="${OMNIFLOW_SMOKE_ORG_ID:-18826643-91da-5dd4-b088-03a36d6f72a5}"
SMOKE_ROLE="${OMNIFLOW_SMOKE_ROLE:-owner}"

request() {
  local method="$1"
  local url="$2"
  local body="${3:-}"

  if [[ -n "${body}" ]]; then
    curl --fail --silent --show-error \
      -X "${method}" \
      -H "Content-Type: application/json" \
      -H "X-Omniflow-User-Id: ${SMOKE_USER_ID}" \
      -H "X-Omniflow-Org-Id: ${SMOKE_ORG_ID}" \
      -H "X-Omniflow-Role: ${SMOKE_ROLE}" \
      -d "${body}" \
      "${url}"
  else
    curl --fail --silent --show-error \
      -X "${method}" \
      -H "X-Omniflow-User-Id: ${SMOKE_USER_ID}" \
      -H "X-Omniflow-Org-Id: ${SMOKE_ORG_ID}" \
      -H "X-Omniflow-Role: ${SMOKE_ROLE}" \
      "${url}"
  fi
}

request GET "${BASE_URL}/healthz" >/dev/null
request GET "${BASE_URL}/healthz/db" >/dev/null
request GET "${BASE_URL}/ready" >/dev/null

campaign_json="$(request POST "${BASE_URL}/campaigns/plan" '{"week_start_date":"2026-03-02","channels":["linkedin"],"objectives":["Render smoke campaign"]}')"
campaign_id="$(python -c 'import json,sys; print(json.load(sys.stdin)["id"])' <<<"${campaign_json}")"

request POST "${BASE_URL}/campaigns/${campaign_id}/generate-content" >/dev/null

content_json="$(request GET "${BASE_URL}/content?limit=1")"
content_id="$(python -c 'import json,sys; payload=json.load(sys.stdin); row=payload[0] if isinstance(payload, list) else payload["items"][0]; print(row["id"])' <<<"${content_json}")"

request POST "${BASE_URL}/content/${content_id}/approve" '{"status":"approved","notes":"render smoke approval"}' >/dev/null

job_json="$(request POST "${BASE_URL}/content/${content_id}/schedule" '{"provider":"linkedin","account_ref":"default"}')"
job_status="$(python -c 'import json,sys; print(json.load(sys.stdin)["status"])' <<<"${job_json}")"

if [[ "${job_status}" != "queued" ]]; then
  echo "Expected queued publish job, got ${job_status}"
  exit 1
fi

echo "render smoke passed"
