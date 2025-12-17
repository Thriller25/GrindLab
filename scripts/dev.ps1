param(
    [switch]$ResetDb,
    [switch]$SmokeOnly
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$BaseUrl = "http://127.0.0.1:8000"
$BackendLog = Join-Path $env:TEMP "grindlab-backend.log"
$BackendErrLog = Join-Path $env:TEMP "grindlab-backend.err.log"
$FrontendLog = Join-Path $env:TEMP "grindlab-frontend.log"
$FrontendErrLog = Join-Path $env:TEMP "grindlab-frontend.err.log"

function Get-PythonExe {
    param([string[]]$Candidates)
    foreach ($path in $Candidates) {
        if ($path -and (Test-Path $path)) {
            return $path
        }
    }
    return "python"
}

$pythonExe = Get-PythonExe @(
    (Join-Path $BackendDir ".venv\Scripts\python.exe"),
    (Join-Path $RepoRoot ".venv\Scripts\python.exe")
)

if ($SmokeOnly -and $ResetDb) {
    throw "-SmokeOnly cannot be combined with -ResetDb. Start services normally, then run -SmokeOnly."
}

function Stop-Port {
    param([int]$Port)
    Write-Host "[dev] Checking port $Port..."
    $lines = netstat -ano -p tcp | Select-String ":$Port"
    foreach ($line in $lines) {
        $parts = $line.ToString().Split(" ", [StringSplitOptions]::RemoveEmptyEntries)
        if ($parts.Count -lt 5) { continue }
        $procId = $parts[-1]
        if ($procId -eq "0") { continue }
        if ($procId -match '^\d+$') {
            try {
                Stop-Process -Id $procId -Force -ErrorAction Stop
                Write-Host "[dev] Killed PID $procId on port $Port"
            } catch {
                Write-Warning ("[dev] Failed to kill PID {0} on port {1}: {2}" -f $procId, $Port, $_)
            }
        }
    }
}

if ($SmokeOnly) {
    Write-Host "[dev] Running smoke checks against existing backend at $BaseUrl ..."
    Push-Location $BackendDir
    & $pythonExe "scripts/smoke_api.py" $BaseUrl
    $smokeExit = $LASTEXITCODE
    Pop-Location
    if ($smokeExit -ne 0) {
        throw "[dev] Smoke checks failed with exit code $smokeExit"
    }
    Write-Host "[dev] Smoke checks passed."
    return
}

Write-Host "[dev] Stopping existing processes on 8000/5173..."
Stop-Port -Port 8000
Stop-Port -Port 5173

if ($ResetDb.IsPresent) {
    Write-Host "[dev] Resetting database..."
    Push-Location $BackendDir
    & $pythonExe "scripts/reset_db.py"
    if ($LASTEXITCODE -ne 0) {
        throw "reset_db.py failed with exit code $LASTEXITCODE"
    }
    Pop-Location
}

Write-Host "[dev] Starting backend (uvicorn --reload)..."
$backendArgs = "-m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000"
$backendProcess = Start-Process -FilePath $pythonExe -ArgumentList $backendArgs -WorkingDirectory $BackendDir -PassThru -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrLog -WindowStyle Hidden
Write-Host "[dev] Backend PID: $($backendProcess.Id) (logs: $BackendLog, $BackendErrLog)"

Write-Host "[dev] Starting frontend (npm run dev)..."
$frontendArgs = "run dev -- --host 0.0.0.0 --port 5173"
$frontendProcess = Start-Process -FilePath "npm.cmd" -ArgumentList $frontendArgs -WorkingDirectory $FrontendDir -PassThru -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrLog -WindowStyle Hidden
Write-Host "[dev] Frontend PID: $($frontendProcess.Id) (logs: $FrontendLog, $FrontendErrLog)"

Write-Host "[dev] Waiting for backend to become healthy at $BaseUrl/health ..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    try {
        $resp = Invoke-WebRequest -Uri "$BaseUrl/health" -UseBasicParsing -TimeoutSec 5
        if ($resp.StatusCode -eq 200) {
            $ready = $true
            break
        }
    } catch {
        Start-Sleep -Seconds 1
    }
}

if (-not $ready) {
    Write-Warning "[dev] Backend did not report healthy. Check $BackendLog"
} else {
    Write-Host "[dev] Backend is up. Running smoke checks..."
    Push-Location $BackendDir
    & $pythonExe "scripts/smoke_api.py" $BaseUrl
    $smokeExit = $LASTEXITCODE
    Pop-Location
    if ($smokeExit -ne 0) {
        Write-Warning "[dev] Smoke checks failed with exit code $smokeExit"
        $smokeFailed = $true
    }
}

if (Test-Path $BackendLog) {
    Write-Host "[dev] --- Backend log tail ---"
    Get-Content $BackendLog -Tail 20
}
if (Test-Path $BackendErrLog) {
    Write-Host "[dev] --- Backend error log tail ---"
    Get-Content $BackendErrLog -Tail 20
}
if (Test-Path $FrontendLog) {
    Write-Host "[dev] --- Frontend log tail ---"
    Get-Content $FrontendLog -Tail 10
}
if (Test-Path $FrontendErrLog) {
    Write-Host "[dev] --- Frontend error log tail ---"
    Get-Content $FrontendErrLog -Tail 10
}

if ($smokeFailed) {
    throw "[dev] Smoke checks failed."
}

Write-Host "[dev] Visit http://localhost:5173 (backend PID $($backendProcess.Id), frontend PID $($frontendProcess.Id))."
Write-Host "[dev] Stop them with: Stop-Process -Id $($backendProcess.Id), $($frontendProcess.Id)"
