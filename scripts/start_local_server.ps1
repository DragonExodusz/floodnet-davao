$ErrorActionPreference = "Stop"

$projectDirectory = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$python = Join-Path $env:USERPROFILE "miniforge3\envs\floodnet-ml\python.exe"
$healthUrl = "http://127.0.0.1:8000/api/health"
$stateDirectory = Join-Path $env:LOCALAPPDATA "FloodNetDavao"
$pidFile = Join-Path $stateDirectory "uvicorn.pid"

if (-not (Test-Path -LiteralPath $python)) {
    Write-Error "FloodNet Python environment not found at $python. Run the 'FloodNet: Create Python environment' VS Code task first."
    exit 1
}

try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
    if ($health.status -eq "ok") {
        Write-Output "FloodNet is already running at http://127.0.0.1:8000"
        exit 0
    }
}
catch {
}

$server = Start-Process `
    -FilePath $python `
    -ArgumentList @("-m", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $projectDirectory `
    -WindowStyle Hidden `
    -PassThru

for ($attempt = 0; $attempt -lt 30; $attempt++) {
    if ($server.HasExited) {
        Write-Error "FloodNet server exited during startup. Check the Python environment and try running the VS Code task in a terminal to see server output."
        exit 1
    }

    try {
        $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 2
        if ($health.status -eq "ok") {
            New-Item -ItemType Directory -Path $stateDirectory -Force | Out-Null
            Set-Content -LiteralPath $pidFile -Value $server.Id -Encoding ascii
            Write-Output "FloodNet is ready at http://127.0.0.1:8000"
            exit 0
        }
    }
    catch {
    }

    Start-Sleep -Seconds 1
}

Stop-Process -Id $server.Id -ErrorAction SilentlyContinue
Write-Error "FloodNet did not become ready at $healthUrl within 30 seconds."
exit 1
