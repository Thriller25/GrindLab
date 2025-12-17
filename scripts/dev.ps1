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

function Get-PortOwningPid {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        if ($conn -and $conn.OwningProcess) {
            return [int]$conn.OwningProcess
        }
    } catch {
        # Ignore and fallback to netstat parsing
    }

    try {
        $lines = netstat -ano -p tcp | Select-String ":$Port" | Where-Object { $_ -match "LISTENING" }
        foreach ($line in $lines) {
            $parts = $line.ToString().Split(" ", [StringSplitOptions]::RemoveEmptyEntries)
            if ($parts.Count -lt 5) { continue }
            $pidPart = $parts[-1]
            if ($pidPart -match '^\d+$' -and $pidPart -ne "0") {
                return [int]$pidPart
            }
        }
    } catch {
        # Ignore parsing failures
    }
    return $null
}

function Stop-PidTree {
    param([int]$ProcessId)
    if (-not $ProcessId) { return }
    Write-Host ("[dev] Stopping PID {0} (Stop-Process -Force)..." -f $ProcessId)
    try {
        Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
    } catch {
        # Ignore
    }
    Write-Host ("[dev] Stopping PID {0} (taskkill /F /T)..." -f $ProcessId)
    try {
        & cmd.exe /c "taskkill /F /T /PID $ProcessId" 1>$null 2>$null
    } catch {
        # Ignore
    }
}

function Stop-PortOwner {
    param(
        [int]$Port,
        [int]$Retries = 5,
        [int]$DelayMs = 300
    )
    Write-Host "[dev] Checking port $Port..."
    for ($i = 1; $i -le $Retries; $i++) {
        $portPid = Get-PortOwningPid -Port $Port
        if (-not $portPid) {
            Write-Host "[dev] Port $Port is free."
            return
        }

        Write-Host ("[dev] Port {0} owned by PID {1} (attempt {2}/{3})" -f $Port, $portPid, $i, $Retries)
        $proc = Get-Process -Id $portPid -ErrorAction SilentlyContinue
        if ($proc) {
            Stop-PidTree -ProcessId $portPid
        } else {
            $children = Get-CimInstance Win32_Process -Filter "ParentProcessId=$portPid" -ErrorAction SilentlyContinue | Select-Object -ExpandProperty ProcessId
            if ($children) {
                Write-Warning ("[dev] PID {0} not found; stopping child PIDs {1}..." -f $portPid, ($children -join ", "))
                foreach ($childPid in $children) {
                    Stop-PidTree -ProcessId $childPid
                }
            } else {
                Write-Warning ("[dev] PID {0} not found in task list; waiting for port release..." -f $portPid)
            }
        }
        Start-Sleep -Milliseconds $DelayMs

        $checkPid = Get-PortOwningPid -Port $Port
        if (-not $checkPid) {
            Write-Host "[dev] Port $Port is now free."
            return
        }
    }

    throw ("[dev] Could not free port {0} after {1} attempts. Check `netstat -ano | findstr :{0}`." -f $Port, $Retries)
}

function Ensure-PortsFree {
    Write-Host "[dev] Ensuring ports 8000 and 5173 are free..."
    Stop-PortOwner -Port 8000 -Retries 10 -DelayMs 500
    try {
        Stop-PortOwner -Port 5173 -Retries 5 -DelayMs 200
    } catch {
        Write-Warning "[dev] Failed to free port 5173: $($_.Exception.Message)"
    }
}

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
Ensure-PortsFree

if ($ResetDb.IsPresent) {
    Write-Host "[dev] Resetting database..."
    Push-Location $BackendDir
    $resetOutput = & $pythonExe "scripts/reset_db.py" 2>&1
    $resetExit = $LASTEXITCODE
    Pop-Location
    if ($resetExit -ne 0) {
        Write-Warning $resetOutput
        if ($resetOutput -match "WinError 32" -or $resetOutput -match "PermissionError") {
            Write-Warning "[dev] reset_db.py failed due to locked file. Retrying after additional port cleanup..."
            Stop-PortOwner -Port 8000 -Retries 8 -DelayMs 400
            Start-Sleep -Milliseconds 500
            Push-Location $BackendDir
            $resetOutput = & $pythonExe "scripts/reset_db.py" 2>&1
            $resetExit = $LASTEXITCODE
            Pop-Location
            if ($resetExit -ne 0) {
                throw "[dev] reset_db.py failed again (possibly locked). Output:`n$resetOutput"
            }
        } else {
            throw "reset_db.py failed with exit code $resetExit`n$resetOutput"
        }
    }
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
