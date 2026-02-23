param(
  [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

if (-not $env:DATABASE_URL) { throw "DATABASE_URL is required" }
if (-not $env:REDIS_URL) { throw "REDIS_URL is required" }
if (-not $env:TOKEN_ENCRYPTION_KEY) { throw "TOKEN_ENCRYPTION_KEY is required" }

Write-Host "Building API image..."
docker build -f apps/api/Dockerfile -t omniflow-api:staging . | Out-Null
Write-Host "Building worker image..."
docker build -f apps/worker/Dockerfile -t omniflow-worker:staging . | Out-Null

Write-Host "Running migrations..."
python -m alembic -c apps/api/alembic.ini upgrade head | Out-Null

Write-Host "Running smoke checks..."
powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1 -BaseUrl $BaseUrl

Write-Host "deploy-check completed"
