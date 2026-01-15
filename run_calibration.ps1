# Quick script to run calibration with correct Python version
# Usage: 
#   .\run_calibration.ps1 --user your_user
#   .\run_calibration.ps1 --user your_user --work-duration 30 --break-duration 5
#   (All arguments are passed directly to the Python script)

$python312 = "C:\Users\ohamj\AppData\Local\Programs\Python\Python312\python.exe"

if (-not (Test-Path $python312)) {
    Write-Host "ERROR: Python 3.12 not found at: $python312" -ForegroundColor Red
    Write-Host "Please update the path in this script or use Python 3.12 directly." -ForegroundColor Yellow
    exit 1
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "Running calibration with Python 3.12..." -ForegroundColor Green
Write-Host "Passing arguments to Python script..." -ForegroundColor Cyan
Write-Host ""

# Pass all arguments directly to the Python script
& $python312 fatigue_detection/calibration_cli.py $args
