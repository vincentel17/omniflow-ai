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

Write-Host "Seeding default tenancy data..."
$env:PYTHONPATH = (Resolve-Path "apps/api").Path
python -m app.seed | Out-Null

Write-Host "Running smoke checks..."

function Remove-StagingContainerIfExists {
  $existing = docker ps -a --filter "name=^/omniflow-api-staging-check$" --format "{{.ID}}"
  if ($existing) {
    docker rm -f omniflow-api-staging-check | Out-Null
  }
}

function Convert-LocalhostForDocker([string]$value) {
  if (-not $value) {
    return $value
  }
  $rewritten = $value.Replace("://localhost", "://host.docker.internal")
  $rewritten = $rewritten.Replace("://127.0.0.1", "://host.docker.internal")
  $rewritten = $rewritten.Replace("@localhost", "@host.docker.internal")
  $rewritten = $rewritten.Replace("@127.0.0.1", "@host.docker.internal")
  return $rewritten
}

$containerDatabaseUrl = Convert-LocalhostForDocker $env:DATABASE_URL
$containerRedisUrl = Convert-LocalhostForDocker $env:REDIS_URL

Remove-StagingContainerIfExists
try {
  docker run -d --name omniflow-api-staging-check --add-host=host.docker.internal:host-gateway -p ${hostPort}:8000 `
    -e DATABASE_URL="$containerDatabaseUrl" `
    -e REDIS_URL="$containerRedisUrl" `
    -e TOKEN_ENCRYPTION_KEY="$env:TOKEN_ENCRYPTION_KEY" `
    omniflow-api:staging | Out-Null
  if ($LASTEXITCODE -ne 0) {
    throw "Failed to start staging API container"
  }

  $healthy = $false
  for ($i = 0; $i -lt 30; $i++) {
    try {
      Invoke-RestMethod -Method GET -Uri "$BaseUrl/ready" | Out-Null
      $healthy = $true
      break
    } catch {
      Start-Sleep -Seconds 1
    }
  }
  if (-not $healthy) {
    Write-Host "Staging API container logs (tail):"
    docker logs --tail 120 omniflow-api-staging-check
    throw "Staging API container failed readiness check at $BaseUrl/ready"
  }

  powershell -ExecutionPolicy Bypass -File scripts/smoke.ps1 -BaseUrl $BaseUrl
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Staging API container logs (tail):"
    docker logs --tail 120 omniflow-api-staging-check
    throw "Smoke checks failed with exit code $LASTEXITCODE"
  }
} finally {
  Remove-StagingContainerIfExists
}

Write-Host "deploy-check completed"
