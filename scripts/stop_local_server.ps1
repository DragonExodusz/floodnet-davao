$ErrorActionPreference = "Stop"

$python = Join-Path $env:USERPROFILE "miniforge3\envs\floodnet-ml\python.exe"
$pidFile = Join-Path $env:LOCALAPPDATA "FloodNetDavao\uvicorn.pid"

if (-not (Test-Path -LiteralPath $pidFile)) {
    Write-Output "No VS Code-managed FloodNet server is running."
    exit 0
}

$serverId = 0
if (-not [int]::TryParse((Get-Content -Raw -LiteralPath $pidFile).Trim(), [ref]$serverId)) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Error "FloodNet server PID file was invalid; removed it without stopping any process."
    exit 1
}

$server = Get-Process -Id $serverId -ErrorAction SilentlyContinue
if ($null -eq $server) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Output "FloodNet server was already stopped."
    exit 0
}

if ($server.Path -ne $python) {
    Remove-Item -LiteralPath $pidFile -Force
    Write-Error "PID $serverId no longer belongs to the FloodNet Python environment; removed the stale PID file without stopping the process."
    exit 1
}

Stop-Process -Id $serverId
Remove-Item -LiteralPath $pidFile -Force
Write-Output "FloodNet server stopped."
