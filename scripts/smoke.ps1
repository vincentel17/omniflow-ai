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

Invoke-Json -Method GET -Url "$BaseUrl/healthz" | Out-Null
Invoke-Json -Method GET -Url "$BaseUrl/healthz/db" | Out-Null
Invoke-Json -Method GET -Url "$BaseUrl/ready" | Out-Null

$campaign = Invoke-Json -Method POST -Url "$BaseUrl/campaigns/plan" -Headers $headers -Body @{
  week_start_date = "2026-03-02"
  channels = @("linkedin")
  objectives = @("Smoke-test campaign")
}
$campaignId = $campaign.id

Invoke-Json -Method POST -Url "$BaseUrl/campaigns/$campaignId/generate-content" -Headers $headers | Out-Null
$content = Invoke-Json -Method GET -Url "$BaseUrl/content?limit=1" -Headers $headers
$contentId = $content[0].id

Invoke-Json -Method POST -Url "$BaseUrl/content/$contentId/approve" -Headers $headers -Body @{
  status = "approved"
  notes = "smoke approval"
} | Out-Null

$job = Invoke-Json -Method POST -Url "$BaseUrl/content/$contentId/schedule" -Headers $headers -Body @{
  provider = "linkedin"
  account_ref = "default"
}
if ($job.status -ne "queued") { throw "Expected queued publish job" }

Write-Host "smoke passed"
