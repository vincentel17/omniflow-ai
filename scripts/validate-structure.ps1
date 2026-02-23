param()

$ErrorActionPreference = "Stop"
$required = @(
  "apps/web",
  "apps/api",
  "apps/worker",
  "packages/ui",
  "packages/config",
  "packages/schemas",
  "packages/events",
  "packages/policy",
  "packages/connectors",
  "packages/verticals",
  "infra",
  "scripts",
  "docs",
  "tests",
  "docker-compose.yml",
  "pnpm-workspace.yaml",
  "package.json",
  "README.md",
  ".github/workflows/ci.yml",
  ".github/pull_request_template.md"
)

$missing = @()
foreach ($path in $required) {
  if (-not (Test-Path $path)) {
    $missing += $path
  }
}

if ($missing.Count -gt 0) {
  Write-Error ("Missing required paths:`n - " + ($missing -join "`n - "))
  exit 1
}

Write-Host "Repository structure validation passed."
