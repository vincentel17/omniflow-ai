param(
  [string]$BaseUrl = "http://localhost:8000"
)

$ErrorActionPreference = "Stop"

function Invoke-Json {
  param(
    [string]$Method,
    [string]$Url,
    [hashtable]$Headers = @{},
    [object]$Body = $null
  )
  if ($Body -ne $null) {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
  }
  return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers
}

$headers = @{
  "X-Omniflow-User-Id" = "11111111-1111-1111-1111-111111111111"
  "X-Omniflow-Org-Id"  = "22222222-2222-2222-2222-222222222222"
  "X-Omniflow-Role"    = "owner"
}

Invoke-Json -Method GET -Url "$BaseUrl/health" | Out-Null
Invoke-Json -Method GET -Url "$BaseUrl/dashboard/ops-summary" -Headers $headers | Out-Null

$campaign = Invoke-Json -Method POST -Url "$BaseUrl/campaigns/plan" -Headers $headers -Body @{
  week_start_date = "2026-03-02"
  channels = @("linkedin")
  objectives = @("Smoke-test campaign")
}
$campaignId = $campaign.id

if (-not $campaignId) { throw "Expected campaign plan id" }

$plans = Invoke-Json -Method GET -Url "$BaseUrl/campaigns/plans" -Headers $headers
if ($null -eq $plans) { throw "Expected campaign plans response" }

Write-Host "smoke passed"
