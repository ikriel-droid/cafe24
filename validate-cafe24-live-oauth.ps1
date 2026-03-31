param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [string]$ManagerEmail = "manager@alpha-seller.local",
  [string]$Password = "demo1234",
  [int]$TimeoutSeconds = 300,
  [switch]$StartAppIfNeeded = $true,
  [switch]$OpenBrowser = $true
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$artifactsDir = Join-Path $root "run-artifacts"
$reportMarkdown = Join-Path $artifactsDir "latest-live-oauth-validation.md"
$reportJson = Join-Path $artifactsDir "latest-live-oauth-validation.json"
$startScript = Join-Path $root "start-claimmate.ps1"
$apiEnv = Join-Path $root "api\.env"

function Get-EnvFileMap {
  param([Parameter(Mandatory = $true)][string]$Path)

  $map = @{}
  if (-not (Test-Path $Path)) {
    return $map
  }

  foreach ($line in Get-Content -Path $Path -Encoding utf8) {
    if ([string]::IsNullOrWhiteSpace($line) -or $line.TrimStart().StartsWith("#") -or -not $line.Contains("=")) {
      continue
    }
    $key, $value = $line.Split("=", 2)
    $map[$key.Trim()] = $value.Trim()
  }

  return $map
}

function Test-HttpReady {
  param([Parameter(Mandatory = $true)][string]$Url)

  try {
    Invoke-WebRequest -UseBasicParsing -Uri $Url | Out-Null
    return $true
  } catch {
    return $false
  }
}

function Write-ValidationArtifacts {
  param([Parameter(Mandatory = $true)][hashtable]$Report)

  New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null

  $lines = @(
    "# Cafe24 Live OAuth Validation Report",
    "",
    ("- generated_at: {0}" -f $Report.generated_at),
    ("- status: {0}" -f $Report.status),
    ("- base_url: {0}" -f $Report.base_url),
    ("- manager_email: {0}" -f $Report.manager_email),
    ("- connected_before: {0}" -f $Report.connected_before),
    ("- connected_after: {0}" -f $Report.connected_after),
    ("- oauth_env_ready: {0}" -f $Report.oauth_env_ready),
    ("- authorize_url: {0}" -f $Report.authorize_url),
    ("- health_title: {0}" -f $Report.health_title),
    ("- access_token_expires_at: {0}" -f $Report.access_token_expires_at),
    "",
    "## Notes",
    ""
  )

  foreach ($note in $Report.notes) {
    $lines += ("- {0}" -f $note)
  }

  $lines | Set-Content -Path $reportMarkdown -Encoding utf8
  $Report | ConvertTo-Json -Depth 6 | Set-Content -Path $reportJson -Encoding utf8
}

$report = [ordered]@{
  generated_at            = (Get-Date).ToString("s")
  status                  = "starting"
  base_url                = $BaseUrl.TrimEnd("/")
  manager_email           = $ManagerEmail
  connected_before        = $false
  connected_after         = $false
  oauth_env_ready         = $false
  authorize_url           = $null
  health_title            = $null
  access_token_expires_at = $null
  notes                   = New-Object System.Collections.Generic.List[string]
}

if (-not (Test-HttpReady -Url "$($report.base_url)/health")) {
  if ($StartAppIfNeeded) {
    & powershell -ExecutionPolicy Bypass -File $startScript | Out-Host
  }
}

if (-not (Test-HttpReady -Url "$($report.base_url)/health")) {
  $report.status = "blocked_app_unavailable"
  $report.notes.Add("ClaimMate API is not reachable. Start the app first.") | Out-Null
  Write-ValidationArtifacts -Report $report
  Write-Host "Validation status: $($report.status)"
  exit 0
}

$envMap = Get-EnvFileMap -Path $apiEnv
$requiredKeys = @("CAFE24_CLIENT_ID", "CAFE24_CLIENT_SECRET", "CAFE24_REDIRECT_URI")
$missingKeys = $requiredKeys | Where-Object { -not $envMap.ContainsKey($_) -or [string]::IsNullOrWhiteSpace($envMap[$_]) }
$report.oauth_env_ready = ($missingKeys.Count -eq 0)

$session = New-Object Microsoft.PowerShell.Commands.WebRequestSession
$loginBody = @{
  email    = $ManagerEmail
  password = $Password
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "$($report.base_url)/api/auth/login" `
  -WebSession $session `
  -ContentType "application/json" `
  -Body $loginBody | Out-Null

$statusBefore = Invoke-RestMethod -Uri "$($report.base_url)/api/integrations/cafe24" -WebSession $session
$report.connected_before = [bool]$statusBefore.connected
$report.health_title = $statusBefore.health_title
$report.authorize_url = $statusBefore.authorize_url
$report.access_token_expires_at = $statusBefore.access_token_expires_at

if (-not $report.oauth_env_ready) {
  $report.status = "blocked_missing_env"
  $report.notes.Add(("Missing required Cafe24 env vars in api/.env: {0}" -f ($missingKeys -join ", "))) | Out-Null
  $report.notes.Add("Fill the env values, rerun this script, and then complete the browser OAuth step.") | Out-Null
  Write-ValidationArtifacts -Report $report
  Write-Host "Validation status: $($report.status)"
  exit 0
}

if (-not $report.authorize_url) {
  $report.status = "blocked_missing_authorize_url"
  $report.notes.Add("Cafe24 authorize URL was not available from the API.") | Out-Null
  Write-ValidationArtifacts -Report $report
  Write-Host "Validation status: $($report.status)"
  exit 0
}

if ($report.connected_before) {
  $report.status = "validated"
  $report.connected_after = $true
  $report.notes.Add("Cafe24 connection was already active before the validation run started.") | Out-Null
  Write-ValidationArtifacts -Report $report
  Write-Host "Validation status: $($report.status)"
  exit 0
}

if ($OpenBrowser) {
  Start-Process $report.authorize_url
  $report.notes.Add("Opened the Cafe24 authorize URL in the default browser.") | Out-Null
} else {
  $report.notes.Add("Browser auto-open was skipped. Use the authorize_url from this report manually.") | Out-Null
}

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
while ((Get-Date) -lt $deadline) {
  Start-Sleep -Seconds 3
  $statusCurrent = Invoke-RestMethod -Uri "$($report.base_url)/api/integrations/cafe24" -WebSession $session
  if ($statusCurrent.connected) {
    $report.status = "validated"
    $report.connected_after = $true
    $report.health_title = $statusCurrent.health_title
    $report.access_token_expires_at = $statusCurrent.access_token_expires_at
    $report.notes.Add("Cafe24 OAuth completed and the connection was saved.") | Out-Null
    Write-ValidationArtifacts -Report $report
    Write-Host "Validation status: $($report.status)"
    exit 0
  }
}

$report.status = "pending_manual_auth"
$report.notes.Add("Cafe24 OAuth did not complete within the wait window.") | Out-Null
$report.notes.Add("Re-run this script after completing the browser flow, or extend TimeoutSeconds.") | Out-Null
Write-ValidationArtifacts -Report $report
Write-Host "Validation status: $($report.status)"
