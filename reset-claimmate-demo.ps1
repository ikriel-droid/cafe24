$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$apiDir = Join-Path $root "api"
$apiPython = Join-Path $apiDir ".venv\\Scripts\\python.exe"

if (-not (Test-Path $apiPython)) {
  throw "Backend virtualenv not found at $apiPython"
}

Push-Location $apiDir
try {
  & $apiPython -m app.scripts.data_lifecycle reset-demo
  if ($LASTEXITCODE -ne 0) {
    throw "Demo reset failed."
  }
} finally {
  Pop-Location
}
