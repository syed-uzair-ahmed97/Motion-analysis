param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = "D:\Motion Analysis"
$pythonPath = Join-Path $projectRoot ".venv\Scripts\python.exe"
$healthUrl = "http://127.0.0.1:8765/api/health"
$websiteUrl = "http://127.0.0.1:8765"

if (-not (Test-Path -LiteralPath $pythonPath)) {
    throw "Python environment not found at $pythonPath"
}
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot "dashboard\dist\index.html"))) {
    throw "The production dashboard build is missing from D:\Motion Analysis."
}

$listeners = Get-NetTCPConnection -State Listen -LocalPort 8765 -ErrorAction SilentlyContinue
foreach ($listener in $listeners) {
    Stop-Process -Id $listener.OwningProcess -Force -ErrorAction SilentlyContinue
}
Start-Sleep -Seconds 1

$arguments = @("-m", "uvicorn", "dashboard.backend:app", "--host", "127.0.0.1", "--port", "8765")
Start-Process -FilePath $pythonPath -ArgumentList $arguments -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null

for ($attempt = 1; $attempt -le 90; $attempt++) {
    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq "ok") {
            if (-not $NoBrowser) {
                Start-Process $websiteUrl
            }
            Write-Host "Motion Analysis reloaded at $websiteUrl"
            exit 0
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

throw "The website did not become ready on port 8765."
