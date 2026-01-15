@echo off
REM Quick batch file to run calibration with Python 3.12
REM Usage: run_calibration.bat your_user

set PYTHON312=C:\Users\ohamj\AppData\Local\Programs\Python\Python312\python.exe
set USER_ID=%1
if "%USER_ID%"=="" set USER_ID=default_user

cd /d "%~dp0"

echo Running calibration with Python 3.12...
echo User: %USER_ID%
echo.

"%PYTHON312%" fatigue_detection\calibration_cli.py --user %USER_ID% --work-duration 30 --break-duration 5
