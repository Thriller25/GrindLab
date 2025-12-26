param(
    [int]$BackendPort = 8001,
    [switch]$NoSeed,
    [switch]$NoBackend,
    [switch]$NoFrontend,
    [switch]$SkipHealth,
    [switch]$ForceKill
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$BackendBaseUrl = "http://127.0.0.1:$BackendPort"
$BackendLog = Join-Path $env:TEMP "grindlab-demo-backend.log"
$BackendErrLog = Join-Path $env:TEMP "grindlab-demo-backend.err.log"
$FrontendLog = Join-Path $env:TEMP "grindlab-demo-frontend.log"
$FrontendErrLog = Join-Path $env:TEMP "grindlab-demo-frontend.err.log"

function Get-PortOwningPid {
    param([int]$Port)
    try {
        $conn = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop | Select-Object -First 1
        if ($conn -and $conn.OwningProcess) {
            return [int]$conn.OwningProcess
        }
    } catch {
        # Ignore
    }

    try {
        $lines = netstat -ano -p tcp | Select-String ":$Port" | Where-Object { $_ -match "LISTENING" }
        foreach ($line in $lines) {
            $parts = $line.ToString().Split(" ", [StringSplitOptions]::RemoveEmptyEntries)
            if ($parts.Count -lt 5) { continue }
            $pidPart = $parts[-1]
            if ($pidPart -match '^[0-9]+$' -and $pidPart -ne "0") { return [int]$pidPart }
        }
    } catch {
        # Ignore
    }
    return $null
}

function Stop-PidTree {
    param([int]$ProcessId)
    if (-not $ProcessId) { return }
    Write-Host "[demo] Stopping PID $ProcessId..." -ForegroundColor DarkYellow
    try { Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue } catch {}
    try { & cmd.exe /c "taskkill /F /T /PID $ProcessId" 1>$null 2>$null } catch {}
}

function Get-PythonExe {
    param([string[]]$Candidates)
    foreach ($path in $Candidates) {
        if ($path -and (Test-Path $path)) { return $path }
    }
    return "python"
}

$pythonExe = Get-PythonExe @(
    (Join-Path $BackendDir ".venv\\Scripts\\python.exe"),
    (Join-Path $RepoRoot ".venv\\Scripts\\python.exe")
)

if (-not $NoBackend) {
    $backendOwner = Get-PortOwningPid -Port $BackendPort
    if ($backendOwner) {
        if ($ForceKill) {
            Stop-PidTree -ProcessId $backendOwner
            Start-Sleep -Milliseconds 300
            $backendOwner = Get-PortOwningPid -Port $BackendPort
        }
        if ($backendOwner) { throw "Порт $BackendPort уже занят PID $backendOwner. Освободите порт или запустите с -BackendPort <port>." }
    }
}

if (-not $NoFrontend) {
    $frontendOwner = Get-PortOwningPid -Port 5173
    if ($frontendOwner) {
        if ($ForceKill) {
            Stop-PidTree -ProcessId $frontendOwner
            Start-Sleep -Milliseconds 300
            $frontendOwner = Get-PortOwningPid -Port 5173
        }
        if ($frontendOwner) { throw "Порт 5173 (frontend) занят PID $frontendOwner. Освободите порт или запустите с -NoFrontend." }
    }
}

if (-not $NoSeed) {
    Write-Host "[demo] Seeding demo data..." -ForegroundColor Cyan
    Push-Location $BackendDir
    $env:PYTHONPATH = $BackendDir
    & $pythonExe "app/demo_seed.py"
    $seedExit = $LASTEXITCODE
    Pop-Location
    if ($seedExit -ne 0) {
        throw "demo_seed.py failed with exit code $seedExit"
    }
    Write-Host "[demo] Demo data seeded." -ForegroundColor Green
}

$backendProcess = $null
if (-not $NoBackend) {
    Write-Host "[demo] Starting backend on $BackendBaseUrl ..." -ForegroundColor Cyan
    $backendArgs = @(
        "-NoProfile",
        "-Command",
        "& { Set-Location '$BackendDir'; $env:PYTHONPATH='$BackendDir'; & '$pythonExe' -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort }"
    )
    $backendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $backendArgs -WorkingDirectory $BackendDir -PassThru -RedirectStandardOutput $BackendLog -RedirectStandardError $BackendErrLog -WindowStyle Hidden
    Write-Host "[demo] Backend PID: $($backendProcess.Id)" -ForegroundColor Yellow
}

$frontendProcess = $null
if (-not $NoFrontend) {
    Write-Host "[demo] Starting frontend (VITE_API_URL=$BackendBaseUrl) ..." -ForegroundColor Cyan
    $frontendArgs = @(
        "-NoProfile",
        "-Command",
        "& { Set-Location '$FrontendDir'; $env:VITE_API_URL='$BackendBaseUrl'; & npm.cmd run dev -- --host 127.0.0.1 --port 5173 }"
    )
    $frontendProcess = Start-Process -FilePath "powershell.exe" -ArgumentList $frontendArgs -WorkingDirectory $FrontendDir -PassThru -RedirectStandardOutput $FrontendLog -RedirectStandardError $FrontendErrLog -WindowStyle Hidden
    Write-Host "[demo] Frontend PID: $($frontendProcess.Id)" -ForegroundColor Yellow
}

if (-not $SkipHealth -and -not $NoBackend) {
    Write-Host "[demo] Waiting for backend health..." -ForegroundColor Cyan
    $healthy = $false
    for ($i = 0; $i -lt 30; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri "$BackendBaseUrl/health" -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { $healthy = $true; break }
        } catch {
            Start-Sleep -Milliseconds 700
        }
    }
    if ($healthy) {
        Write-Host "[demo] Backend is healthy at $BackendBaseUrl/health" -ForegroundColor Green
    } else {
        Write-Warning "[demo] Backend did not respond healthy within timeout. Check logs: $BackendLog, $BackendErrLog"
    }
}

if ($backendProcess) {
    Write-Host "[demo] Backend log (tail):" -ForegroundColor Gray
    if (Test-Path $BackendLog) { Get-Content $BackendLog -Tail 15 }
    if (Test-Path $BackendErrLog) { Get-Content $BackendErrLog -Tail 15 }
}

if ($frontendProcess) {
    Write-Host "[demo] Frontend log (tail):" -ForegroundColor Gray
    if (Test-Path $FrontendLog) { Get-Content $FrontendLog -Tail 10 }
    if (Test-Path $FrontendErrLog) { Get-Content $FrontendErrLog -Tail 10 }
}

Write-Host "[demo] Ready for presentation:" -ForegroundColor Green
if (-not $NoBackend) { Write-Host "  Backend:  $BackendBaseUrl (PID $($backendProcess.Id))" }
if (-not $NoFrontend) { Write-Host "  Frontend: http://localhost:5173 (PID $($frontendProcess.Id))" }
if ($backendProcess -or $frontendProcess) {
    Write-Host "  Stop with: Stop-Process -Id $($backendProcess?.Id), $($frontendProcess?.Id)"
}
