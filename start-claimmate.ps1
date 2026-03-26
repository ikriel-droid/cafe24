$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root "api"
$webDir = Join-Path $root "web"
$apiPython = Join-Path $apiDir ".venv\Scripts\python.exe"

$apiLog = Join-Path $apiDir ".codex-backend.log"
$apiErrLog = Join-Path $apiDir ".codex-backend.err.log"
$webOutDir = Join-Path $webDir "out"

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

function Stop-PortProcess {
  param([Parameter(Mandatory = $true)][int]$Port)

  $lines = cmd.exe /c "netstat -ano -p tcp | findstr LISTENING | findstr :$Port"
  foreach ($line in $lines) {
    $parts = ($line -split "\s+") | Where-Object { $_ }
    if ($parts.Length -ge 5) {
      $processId = $parts[-1]
      try {
        Stop-Process -Id ([int]$processId) -Force -ErrorAction Stop
      } catch {
      }
    }
  }
}

if (-not (Test-Path $apiPython)) {
  throw "Backend virtualenv not found at $apiPython"
}

if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
  throw "Frontend dependencies are not installed. Run 'npm.cmd install' in $webDir first."
}

Stop-PortProcess -Port 8000
Stop-PortProcess -Port 3000

Remove-Item $apiLog, $apiErrLog -ErrorAction SilentlyContinue

if (-not (Test-Path (Join-Path $webOutDir "index.html"))) {
  Push-Location $webDir
  try {
    & cmd.exe /c "npm.cmd run build"
    if ($LASTEXITCODE -ne 0) {
      throw "Frontend build failed."
    }
  } finally {
    Pop-Location
  }
} else {
  Write-Host "Using existing frontend build from $webOutDir"
}

$apiProcess = Start-Process `
  -FilePath $apiPython `
  -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000" `
  -WorkingDirectory $apiDir `
  -RedirectStandardOutput $apiLog `
  -RedirectStandardError $apiErrLog `
  -PassThru

$apiReady = Wait-ForHttp -Url "http://127.0.0.1:8000/health"
$webReady = Wait-ForHttp -Url "http://127.0.0.1:8000/dashboard/"

Write-Host "ClaimMate AI launch requested."
Write-Host "API PID: $($apiProcess.Id)"
Write-Host "API:  http://127.0.0.1:8000/health"
Write-Host "Web:  http://127.0.0.1:8000/dashboard/"

if (-not $apiReady) {
  throw "Backend did not become ready. Check $apiErrLog"
}

if (-not $webReady) {
  throw "Frontend did not become ready through the backend. Check $apiErrLog"
}

Write-Host "ClaimMate AI is ready."
