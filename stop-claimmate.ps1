$ErrorActionPreference = "SilentlyContinue"

$ports = @(8000, 3000)
$processIds = @()

foreach ($port in $ports) {
  $lines = cmd.exe /c "netstat -ano -p tcp | findstr LISTENING | findstr :$port"
  foreach ($line in $lines) {
    $parts = ($line -split "\s+") | Where-Object { $_ }
    if ($parts.Length -ge 5) {
      $processId = [int]$parts[-1]
      if ($processIds -notcontains $processId) {
        $processIds += $processId
      }
    }
  }
}

foreach ($processId in $processIds) {
  Stop-Process -Id $processId -Force
}

Write-Host "ClaimMate AI listeners on ports 8000 and 3000 were stopped."
