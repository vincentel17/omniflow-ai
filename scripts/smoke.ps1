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
    try {
      return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
    } catch {
      Write-Host "Smoke request failed: $Method $Url"
      if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
      throw
    }
  }
  try {
    return Invoke-RestMethod -Method $Method -Uri $Url -Headers $Headers
  } catch {
    Write-Host "Smoke request failed: $Method $Url"
    if ($_.ErrorDetails.Message) { Write-Host $_.ErrorDetails.Message }
    throw
  }
}

$headers = @{
  "X-Omniflow-User-Id" = "11111111-1111-1111-1111-111111111111"
  "X-Omniflow-Org-Id"  = "22222222-2222-2222-2222-222222222222"
  "X-Omniflow-Role"    = "owner"
}

Invoke-Json -Method GET -Url "$BaseUrl/health" | Out-Null
Invoke-Json -Method GET -Url "$BaseUrl/ready" | Out-Null
Invoke-Json -Method GET -Url "$BaseUrl/healthz" | Out-Null
Invoke-Json -Method GET -Url "$BaseUrl/healthz/db" | Out-Null

$weekStartDate = (Get-Date).ToUniversalTime().Date.AddDays((Get-Random -Minimum 1 -Maximum 3650)).ToString("yyyy-MM-dd")
$campaign = Invoke-Json -Method POST -Url "$BaseUrl/campaigns/plan" -Headers $headers -Body @{
  week_start_date = $weekStartDate
  channels = @("linkedin")
  objectives = @("Smoke-test campaign")
}
$campaignId = $campaign.id

if (-not $campaignId) { throw "Expected campaign plan id" }

$plans = Invoke-Json -Method GET -Url "$BaseUrl/campaigns" -Headers $headers
if ($null -eq $plans) { throw "Expected campaign plans response" }

Write-Host "smoke passed"
