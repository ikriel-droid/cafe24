param(
  [string[]]$Stage = "all",
  [switch]$ForceInstall,
  [switch]$SkipDocker,
  [int]$SmokeClaimId = 1
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root "api"
$webDir = Join-Path $root "web"
$apiPython = Join-Path $apiDir ".venv\Scripts\python.exe"
$startScript = Join-Path $root "start-claimmate.ps1"
$stopScript = Join-Path $root "stop-claimmate.ps1"
$artifactsDir = Join-Path $root "run-artifacts"
$reportMarkdown = Join-Path $artifactsDir "latest-completion-report.md"
$reportJson = Join-Path $artifactsDir "latest-completion-report.json"

$script:StageResults = New-Object System.Collections.Generic.List[object]
$script:SmokeSummary = $null
$script:RoadmapLines = @()
$script:DockerStageNote = "Docker stage not run."

function Write-StageHeader {
  param([Parameter(Mandatory = $true)][string]$Name)
  Write-Host ""
  Write-Host ("=== {0} ===" -f $Name)
}

function Add-StageResult {
  param(
    [Parameter(Mandatory = $true)][string]$Name,
    [Parameter(Mandatory = $true)][string]$Status,
    [object]$Note = ""
  )

  $noteText = if ($null -eq $Note) {
    ""
  } elseif ($Note -is [System.Array]) {
    (($Note | Where-Object { $_ -ne $null } | ForEach-Object { $_.ToString().Trim() } | Where-Object { $_ }) -join " | ")
  } else {
    $Note.ToString().Trim()
  }

  $script:StageResults.Add([pscustomobject]@{
      stage      = $Name
      status     = $Status
      note       = $noteText
      recordedAt = (Get-Date).ToString("s")
    }) | Out-Null
}

function Invoke-CheckedCommand {
  param(
    [Parameter(Mandatory = $true)][string]$WorkingDirectory,
    [Parameter(Mandatory = $true)][string]$FilePath,
    [string[]]$Arguments = @()
  )

  Push-Location $WorkingDirectory
  try {
    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
      throw ("Command failed with exit code {0}: {1} {2}" -f $LASTEXITCODE, $FilePath, ($Arguments -join " "))
    }
  } finally {
    Pop-Location
  }
}

function Resolve-BootstrapPython {
  $python312 = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
  if (Test-Path $python312) {
    return @($python312)
  }

  $py = Get-Command py -ErrorAction SilentlyContinue
  if ($py) {
    return @($py.Source, "-3.12")
  }

  $python = Get-Command python -ErrorAction SilentlyContinue
  if ($python) {
    return @($python.Source)
  }

  throw "Python 3.12 launcher was not found. Install Python 3.12 first."
}

function Ensure-EnvFile {
  param(
    [Parameter(Mandatory = $true)][string]$TargetPath,
    [Parameter(Mandatory = $true)][string]$ExamplePath
  )

  if (-not (Test-Path $TargetPath)) {
    Copy-Item $ExamplePath $TargetPath
    Write-Host ("Created {0}" -f $TargetPath)
  }
}

function Wait-ForHttp {
  param(
    [Parameter(Mandatory = $true)][string]$Url,
    [int]$Attempts = 20,
    [int]$DelaySeconds = 1
  )

  for ($attempt = 0; $attempt -lt $Attempts; $attempt++) {
    try {
      Invoke-WebRequest -UseBasicParsing $Url | Out-Null
      return $true
    } catch {
      Start-Sleep -Seconds $DelaySeconds
    }
  }

  return $false
}

function Get-RoadmapLines {
  return @(
    "Automated completion path in this repository:",
    "1. prepare: create env files, backend venv, backend deps, frontend deps",
    "2. docker: start postgres/redis when Docker is available",
    "3. test: run backend pytest suite",
    "4. build: run frontend production build",
    "5. start: launch the local app at http://127.0.0.1:8000/dashboard/",
    "6. smoke: verify health, seeded claims, policy, mock sync, classify, and draft reply",
    "7. report: write a local completion report to run-artifacts/latest-completion-report.md",
    "",
    "Remaining manual blockers to reach a production-complete ClaimMate AI:",
    "- Cafe24 partner approval and official live API credentials",
    "- Real Cafe24 endpoint mapping for OAuth, orders, claims, and webhooks",
    "- Production identity, password recovery, and stronger operator security controls",
    "- OpenAI production provider rollout, prompt governance, and quality review policy",
    "- Deployment, observability, scheduled backups, and incident handling",
    "- Payment/billing, audit retention, and security review before external rollout"
  )
}

function Invoke-PrepareStage {
  Write-StageHeader "prepare"

  Ensure-EnvFile -TargetPath (Join-Path $root ".env") -ExamplePath (Join-Path $root ".env.example")
  Ensure-EnvFile -TargetPath (Join-Path $apiDir ".env") -ExamplePath (Join-Path $apiDir ".env.example")
  Ensure-EnvFile -TargetPath (Join-Path $webDir ".env.local") -ExamplePath (Join-Path $webDir ".env.example")

  if ($ForceInstall -or -not (Test-Path $apiPython)) {
    $bootstrap = Resolve-BootstrapPython
    $bootstrapArgs = @()
    if ($bootstrap.Length -gt 1) {
      $bootstrapArgs = $bootstrap[1..($bootstrap.Length - 1)]
    }
    Push-Location $apiDir
    try {
      & $bootstrap[0] @($bootstrapArgs + @("-m", "venv", ".venv"))
      if ($LASTEXITCODE -ne 0) {
        throw "Failed to create backend virtualenv."
      }
    } finally {
      Pop-Location
    }
  }

  $backendDepsReady = $false
  if (-not $ForceInstall -and (Test-Path $apiPython)) {
    Push-Location $apiDir
    try {
      & $apiPython -c "import fastapi, pytest, sqlalchemy" | Out-Null
      $backendDepsReady = ($LASTEXITCODE -eq 0)
    } finally {
      Pop-Location
    }
  }

  if ($ForceInstall -or -not $backendDepsReady) {
    Invoke-CheckedCommand -WorkingDirectory $apiDir -FilePath $apiPython -Arguments @("-m", "pip", "install", "--upgrade", "pip") | Out-Host
    Invoke-CheckedCommand -WorkingDirectory $apiDir -FilePath $apiPython -Arguments @("-m", "pip", "install", "-e", ".[dev]") | Out-Host
  } else {
    Write-Host "Using existing backend environment."
  }

  $nodeModules = Join-Path $webDir "node_modules"
  if ($ForceInstall -or -not (Test-Path $nodeModules)) {
    Invoke-CheckedCommand -WorkingDirectory $webDir -FilePath "cmd.exe" -Arguments @("/c", "npm.cmd", "install") | Out-Host
  } else {
    Write-Host ("Using existing frontend dependencies from {0}" -f $nodeModules)
  }

  return "env files ready, backend venv ready, dependencies available"
}

function Invoke-DockerStage {
  Write-StageHeader "docker"

  if ($SkipDocker) {
    Write-Host "Docker stage skipped by request."
    $script:DockerStageNote = "Skipped by request. Using SQLite fallback."
    return $script:DockerStageNote
  }

  $docker = Get-Command docker -ErrorAction SilentlyContinue
  if (-not $docker) {
    Write-Host "Docker not found. Skipping postgres/redis startup and relying on SQLite fallback."
    $script:DockerStageNote = "Docker not installed. Using SQLite fallback."
    return $script:DockerStageNote
  }

  Invoke-CheckedCommand -WorkingDirectory $root -FilePath $docker.Source -Arguments @("compose", "up", "-d", "postgres", "redis") | Out-Host
  $script:DockerStageNote = "Docker Compose started postgres and redis."
  return $script:DockerStageNote
}

function Invoke-TestStage {
  Write-StageHeader "test"
  Invoke-CheckedCommand -WorkingDirectory $apiDir -FilePath $apiPython -Arguments @("-m", "pytest", "-q") | Out-Host
  return "backend pytest passed"
}

function Invoke-BuildStage {
  Write-StageHeader "build"
  $usedExistingBuild = $false
  try {
    Invoke-CheckedCommand -WorkingDirectory $webDir -FilePath "cmd.exe" -Arguments @("/c", "npm.cmd", "run", "build") | Out-Host
  } catch {
    $existingBuild = Join-Path $webDir "out\index.html"
    if (Test-Path $existingBuild) {
      Write-Warning ("Frontend build failed, but an existing exported build is available at {0}. Reusing it." -f $existingBuild)
      $usedExistingBuild = $true
    } else {
      throw
    }
  }

  if ($usedExistingBuild) {
    return "frontend build reused existing exported output"
  }

  return "frontend production build passed"
}

function Invoke-StartStage {
  Write-StageHeader "start"
  Invoke-CheckedCommand -WorkingDirectory $root -FilePath "powershell.exe" -Arguments @("-ExecutionPolicy", "Bypass", "-File", $startScript) | Out-Host
  return "app started at http://127.0.0.1:8000/dashboard/"
}

function Invoke-SmokeStage {
  Write-StageHeader "smoke"

  $healthReady = Wait-ForHttp -Url "http://127.0.0.1:8000/health" -Attempts 25 -DelaySeconds 1
  if (-not $healthReady) {
    Write-Warning "ClaimMate AI was not ready for smoke checks. Re-running local start once."
    Invoke-CheckedCommand -WorkingDirectory $root -FilePath "powershell.exe" -Arguments @("-ExecutionPolicy", "Bypass", "-File", $startScript) | Out-Host
    $healthReady = Wait-ForHttp -Url "http://127.0.0.1:8000/health" -Attempts 25 -DelaySeconds 1
  }

  if (-not $healthReady) {
    throw "ClaimMate AI did not become ready on http://127.0.0.1:8000/health"
  }

  $health = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health"
  $claims = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/claims"
  $summary = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/dashboard/summary"
  $policy = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/policy"
  $sync = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/integrations/cafe24/mock-sync" -Method Post
  $webhook = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/integrations/cafe24/mock-webhook" -Method Post -Body '{"event_type":"delivery.delay.reported","order_no":"CM-240301-006"}' -ContentType "application/json"
  $classification = Invoke-RestMethod -Uri ("http://127.0.0.1:8000/api/claims/{0}/classify" -f $SmokeClaimId) -Method Post
  $draft = Invoke-RestMethod -Uri ("http://127.0.0.1:8000/api/claims/{0}/draft-reply" -f $SmokeClaimId) -Method Post

  if ($claims.Count -lt 1) {
    throw "Smoke test expected seeded claims but received an empty list."
  }

  Write-Host ("health: {0} ({1})" -f $health.status, $health.environment)
  Write-Host ("claims: {0}" -f $claims.Count)
  Write-Host ("summary total/open: {0}/{1}" -f $summary.total_claims, ($summary.open_claims + $summary.in_review_claims))
  Write-Host ("policy exchange/return window: {0}/{1}" -f $policy.exchange_window_days, $policy.return_window_days)
  Write-Host ("mock sync result: {0}" -f $sync.last_sync_result)
  Write-Host ("mock webhook pending count: {0}" -f $webhook.pending_webhooks)
  Write-Host ("classify: claim {0} -> {1}/{2}" -f $classification.claim_id, $classification.category, $classification.urgency)
  Write-Host ("draft reply confidence: {0}" -f $draft.confidence)
  Write-Host "web: http://127.0.0.1:8000/dashboard/"

  $script:SmokeSummary = [pscustomobject]@{
    checkedAt               = (Get-Date).ToString("s")
    healthStatus            = $health.status
    environment             = $health.environment
    claimCount              = $claims.Count
    totalClaims             = $summary.total_claims
    openAndInReviewClaims   = ($summary.open_claims + $summary.in_review_claims)
    exchangeWindowDays      = $policy.exchange_window_days
    returnWindowDays        = $policy.return_window_days
    mockSyncResult          = $sync.last_sync_result
    mockWebhookPendingCount = $webhook.pending_webhooks
    classificationCategory  = $classification.category
    classificationUrgency   = $classification.urgency
    draftReplyConfidence    = $draft.confidence
    appUrl                  = "http://127.0.0.1:8000/dashboard/"
    healthUrl               = "http://127.0.0.1:8000/health"
  }

  return ("health ok, {0} claims, sync {1}" -f $claims.Count, $sync.last_sync_result)
}

function Invoke-RoadmapStage {
  Write-StageHeader "roadmap"

  $script:RoadmapLines = Get-RoadmapLines
  $script:RoadmapLines | ForEach-Object { Write-Host $_ }
  return "printed remaining manual blockers"
}

function Invoke-ReportStage {
  Write-StageHeader "report"

  New-Item -ItemType Directory -Path $artifactsDir -Force | Out-Null

  $timestamp = Get-Date
  $smokeLines = if ($script:SmokeSummary) {
    @(
      "- health: $($script:SmokeSummary.healthStatus) ($($script:SmokeSummary.environment))"
      "- claims: $($script:SmokeSummary.claimCount)"
      "- open + in_review: $($script:SmokeSummary.openAndInReviewClaims)"
      "- policy windows: exchange $($script:SmokeSummary.exchangeWindowDays) / return $($script:SmokeSummary.returnWindowDays)"
      "- mock sync result: $($script:SmokeSummary.mockSyncResult)"
      "- mock webhook pending count: $($script:SmokeSummary.mockWebhookPendingCount)"
      "- classify sample: $($script:SmokeSummary.classificationCategory) / $($script:SmokeSummary.classificationUrgency)"
      "- draft reply confidence: $($script:SmokeSummary.draftReplyConfidence)"
    )
  } else {
    @("- smoke stage not run")
  }

  $stageLines = if ($script:StageResults.Count -gt 0) {
    $script:StageResults | ForEach-Object {
      if ([string]::IsNullOrWhiteSpace($_.note)) {
        "- {0}: {1}" -f $_.stage, $_.status
      } else {
        "- {0}: {1} ({2})" -f $_.stage, $_.status, $_.note
      }
    }
  } else {
    @("- no stages recorded")
  }

  $roadmapLines = if ($script:RoadmapLines.Count -gt 0) {
    $script:RoadmapLines
  } else {
    Get-RoadmapLines
  }

  $markdown = @(
    "# ClaimMate AI Local Completion Report"
    ""
    "- Generated at: $($timestamp.ToString('yyyy-MM-dd HH:mm:ss zzz'))"
    "- Repo: $root"
    "- App URL: http://127.0.0.1:8000/dashboard/"
    "- Health URL: http://127.0.0.1:8000/health"
    "- Docker note: $($script:DockerStageNote)"
    ""
    "## Stage Results"
  ) + $stageLines + @(
    ""
    "## Smoke Summary"
  ) + $smokeLines + @(
    ""
    "## Remaining Manual Work"
  ) + $roadmapLines

  Set-Content -Path $reportMarkdown -Value $markdown -Encoding UTF8

  $reportObject = [pscustomobject]@{
    generated_at = $timestamp.ToString("o")
    repo_root = $root
    app_url = "http://127.0.0.1:8000/dashboard/"
    health_url = "http://127.0.0.1:8000/health"
    docker_note = $script:DockerStageNote
    stages = $script:StageResults
    smoke = $script:SmokeSummary
    remaining_manual_work = $roadmapLines
  }
  $reportObject | ConvertTo-Json -Depth 6 | Set-Content -Path $reportJson -Encoding UTF8

  Write-Host ("Wrote {0}" -f $reportMarkdown)
  Write-Host ("Wrote {0}" -f $reportJson)

  return ("wrote completion report to {0}" -f $artifactsDir)
}

function Invoke-StopStage {
  Write-StageHeader "stop"
  Invoke-CheckedCommand -WorkingDirectory $root -FilePath "powershell.exe" -Arguments @("-ExecutionPolicy", "Bypass", "-File", $stopScript) | Out-Host
  return "stopped listeners on ports 8000 and 3000"
}

$requestedStages = if ($Stage -contains "all") {
  @("prepare", "docker", "test", "build", "start", "smoke", "roadmap", "report")
} else {
  @($Stage | ForEach-Object { $_ -split "\s*,\s*" } | Where-Object { $_ })
}

$validStages = @("prepare", "docker", "test", "build", "start", "smoke", "roadmap", "report", "stop", "all")
$unknownStages = $requestedStages | Where-Object { $_ -notin $validStages }
if ($unknownStages.Count -gt 0) {
  throw ("Unsupported stage value(s): {0}" -f ($unknownStages -join ", "))
}

$shouldWriteReport = $requestedStages -contains "report"
$executionStages = $requestedStages | Where-Object { $_ -ne "report" }
$runError = $null

foreach ($currentStage in $executionStages) {
  try {
    $stageNote = switch ($currentStage) {
      "prepare" { Invoke-PrepareStage }
      "docker" { Invoke-DockerStage }
      "test" { Invoke-TestStage }
      "build" { Invoke-BuildStage }
      "start" { Invoke-StartStage }
      "smoke" { Invoke-SmokeStage }
      "roadmap" { Invoke-RoadmapStage }
      "stop" { Invoke-StopStage }
      default { throw ("Unsupported stage: {0}" -f $currentStage) }
    }

    Add-StageResult -Name $currentStage -Status "completed" -Note $stageNote
  } catch {
    Add-StageResult -Name $currentStage -Status "failed" -Note $_.Exception.Message
    $runError = $_
    break
  }
}

if ($shouldWriteReport) {
  try {
    $reportNote = Invoke-ReportStage
    Add-StageResult -Name "report" -Status "completed" -Note $reportNote
  } catch {
    Add-StageResult -Name "report" -Status "failed" -Note $_.Exception.Message
    if (-not $runError) {
      $runError = $_
    }
  }
}

if ($runError) {
  throw $runError.Exception
}
