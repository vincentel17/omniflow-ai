#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

OUT="${1:-backup-$(date +%Y%m%d-%H%M%S).dump}"
pg_dump --format=custom --no-owner --no-privileges --dbname="$DATABASE_URL" --file="$OUT"
echo "Backup written to $OUT"
