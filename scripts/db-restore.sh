#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${DATABASE_URL:-}" ]]; then
  echo "DATABASE_URL is required"
  exit 1
fi

IN="${1:-}"
if [[ -z "$IN" ]]; then
  echo "Usage: scripts/db-restore.sh <backup.dump>"
  exit 1
fi

pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$DATABASE_URL" "$IN"
echo "Restore completed from $IN"
