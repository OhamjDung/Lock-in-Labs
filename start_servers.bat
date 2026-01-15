@echo off
REM Start Both Servers Script (Batch File)
REM Starts backend API on port 8000 and fatigue detection server on port 8001

echo ========================================
echo Starting Lock In Labs Servers
echo ========================================
echo.

REM Get the script directory
cd /d "%~dp0"

REM Start Backend API on port 8000 in a new window
echo [1/2] Starting Backend API on port 8000...
start "Backend API (Port 8000)" cmd /k "cd /d %~dp0 && echo Backend API Server (Port 8000) && echo Press CTRL+C to stop && uvicorn backend.api:app --reload --port 8000"

REM Wait a moment for the first server to start
timeout /t 3 /nobreak >nul

REM Start Fatigue Detection Server on port 8001
echo [2/2] Starting Fatigue Detection Server on port 8001...
set FATIGUE_PORT=8001
python fatigue_detection/app.py

echo.
echo ========================================
echo Servers Started:
echo   Backend API:        http://localhost:8000
echo   Fatigue Detection:  http://localhost:8001
echo ========================================
