param()

$ErrorActionPreference = "Stop"

function Assert-Command($name) {
  if (-not (Get-Command $name -ErrorAction SilentlyContinue)) {
    throw "Missing required command: $name"
  }
}

function Assert-Version($actual, $expected, $name) {
  if ($actual -ne $expected) {
    throw "$name version mismatch. Expected $expected, got $actual"
  }
}

Assert-Command "node"
Assert-Command "pnpm"
Assert-Command "python"
Assert-Command "docker"

$nodeVersion = (node --version).Trim().TrimStart("v")
$pnpmVersion = (pnpm --version).Trim()
$pythonVersion = ((python --version) -replace "Python ", "").Trim()

$expectedNode = "20.18.0"
$expectedPnpm = "9.12.2"
$expectedPythonMajorMinor = "3.12"

Assert-Version $nodeVersion $expectedNode "Node"
Assert-Version $pnpmVersion $expectedPnpm "pnpm"
if (-not $pythonVersion.StartsWith($expectedPythonMajorMinor)) {
  throw "Python version mismatch. Expected $expectedPythonMajorMinor.x, got $pythonVersion"
}

if (-not (Test-Path ".env")) {
  throw "Missing .env file. Copy .env.example to .env first."
}
if (-not (Test-Path ".env.schema.json")) {
  throw "Missing .env.schema.json"
}

$schema = Get-Content ".env.schema.json" | ConvertFrom-Json
$envMap = @{}
Get-Content ".env" | ForEach-Object {
  if ($_ -match '^\s*#' -or $_ -match '^\s*$') { return }
  $parts = $_.Split('=', 2)
  if ($parts.Count -eq 2) { $envMap[$parts[0]] = $parts[1] }
}

$missingVars = @()
foreach ($key in $schema.required) {
  if (-not $envMap.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($envMap[$key])) {
    $missingVars += $key
  }
}
if ($missingVars.Count -gt 0) {
  throw ("Missing required .env vars: " + ($missingVars -join ", "))
}

$composeVersionOutput = docker compose version
if ($LASTEXITCODE -ne 0) {
  throw "docker compose plugin unavailable"
}

Write-Host "Starting docker compose dependencies for health checks..."
docker compose up -d postgres redis | Out-Null
if ($LASTEXITCODE -ne 0) {
  throw "docker compose up failed"
}

$maxAttempts = 30
$services = @("postgres", "redis")
foreach ($svc in $services) {
  $healthy = $false
  for ($i = 0; $i -lt $maxAttempts; $i++) {
    $status = docker inspect --format='{{.State.Health.Status}}' "omniflow-$svc" 2>$null
    if ($status -eq "healthy") {
      $healthy = $true
      break
    }
    Start-Sleep -Seconds 2
  }
  if (-not $healthy) {
    throw "Service not healthy: $svc"
  }
}

Write-Host "Preflight checks passed."
