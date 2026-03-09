param(
  [string]$BaseUrl = ""
)

$ErrorActionPreference = "Stop"

if (-not $env:DATABASE_URL) { throw "DATABASE_URL is required" }
if (-not $env:REDIS_URL) { throw "REDIS_URL is required" }
if (-not $env:TOKEN_ENCRYPTION_KEY) { throw "TOKEN_ENCRYPTION_KEY is required" }

if (-not $BaseUrl) {
  $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 0)
  $listener.Start()
  $freePort = ([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
  $listener.Stop()
  $BaseUrl = "http://127.0.0.1:$freePort"
}

$baseUri = [uri]$BaseUrl
$hostPort = $baseUri.Port

Write-Host "Building API image..."
docker build -f apps/api/Dockerfile -t omniflow-api:staging . | Out-Null
Write-Host "Building worker image..."
docker build -f apps/worker/Dockerfile -t omniflow-worker:staging . | Out-Null

Write-Host "Running migrations..."
python -m alembic -c apps/api/alembic.ini upgrade head | Out-Null

Write-Host "Running smoke checks..."

function Remove-StagingContainerIfExists {
  $existing = docker ps -a --filter "name=^/omniflow-api-staging-check$" --format "{{.ID}}"
  if ($existing) {
    docker rm -f omniflow-api-staging-check | Out-Null
  }
}

Remove-StagingContainerIfExists
try {
  docker run -d --name omniflow-api-staging-check -p ${hostPort}:8000 `
    -e DATABASE_URL="$env:DATABASE_URL" `
    -e REDIS_URL="$env:REDIS_URL" `
    -e TOKEN_ENCRYPTION_KEY="$env:TOKEN_ENCRYPTION_KEY" `
    omniflow-api:staging | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to start staging API container"
  }

  $healthy = $false
  for ($i = 0; $i -lt 30; $i++) {
    try {
      Invoke-RestMethod -Method GET -Uri "$BaseUrl/health" | Out-Null
      $healthy = $true
      break
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  if (-not $healthy) {
    throw "Staging API container failed health check at $BaseUrl/health"
  }

  powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1 -BaseUrl $BaseUrl
  if ($LASTEXITCODE -ne 0) {
    throw "Smoke checks failed with exit code $LASTEXITCODE"
  }
} finally {
  Remove-StagingContainerIfExists
}

Write-Host "deploy-check completed"
