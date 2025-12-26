@echo off
REM GrindLab Demo Startup Script (Windows)
REM Usage: scripts\demo-up.ps1 [clean]

setlocal enabledelayedexpansion
cd /d "%~dp0\.."

set COMPOSE_FILE=docker-compose.demo.yml

if not exist "%COMPOSE_FILE%" (
    echo ❌ Error: %COMPOSE_FILE% not found
    exit /b 1
)

REM Check if Docker is running
docker ps >nul 2>&1
if errorlevel 1 (
    echo ❌ Error: Docker is not running. Start Docker and try again.
    exit /b 1
)

REM Clean option
if "%1"=="clean" (
    echo 🗑️  Cleaning up containers and volumes...
    docker-compose -f "%COMPOSE_FILE%" down -v
    docker volume rm grindlab-demo-db 2>nul
)

echo 🚀 Starting GrindLab Demo...
echo    Building images and starting services...
docker-compose -f "%COMPOSE_FILE%" up --build

echo.
echo ✅ GrindLab Demo is ready!
echo.
echo    Frontend:  http://localhost:5173
echo    Backend:   http://localhost:8001
echo    Health:    http://localhost:8001/health
echo.
echo Stop with: Ctrl+C or 'docker-compose -f docker-compose.demo.yml down'
