# Start Both Servers Script
# Starts backend API on port 8000 and fatigue detection server on port 8001

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Starting Lock In Labs Servers" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get the script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Start Backend API on port 8000
Write-Host "[1/2] Starting Backend API on port 8000..." -ForegroundColor Green
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$scriptDir'; Write-Host 'Backend API Server (Port 8000)' -ForegroundColor Yellow; Write-Host 'Press CTRL+C to stop' -ForegroundColor Gray; uvicorn backend.api:app --reload --port 8000"
) -WindowStyle Normal

# Wait a moment for the first server to start
Start-Sleep -Seconds 3

# Start Fatigue Detection Server on port 8001
Write-Host "[2/2] Starting Fatigue Detection Server on port 8001..." -ForegroundColor Green
$env:FATIGUE_PORT = "8001"
python fatigue_detection/app.py

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Servers Started:" -ForegroundColor Cyan
Write-Host "  Backend API:        http://localhost:8000" -ForegroundColor White
Write-Host "  Fatigue Detection:  http://localhost:8001" -ForegroundColor White
Write-Host "========================================" -ForegroundColor Cyan
