# Server Setup Guide

This project runs two separate FastAPI servers that need to run simultaneously:

1. **Backend API** (port 8000) - Main application server
2. **Fatigue Detection Server** (port 8001) - Camera-based fatigue detection service

## Quick Start

### Windows (PowerShell) - Recommended
```powershell
.\start_servers.ps1
```

### Windows (Command Prompt)
```cmd
start_servers.bat
```

### Linux/Mac
```bash
chmod +x start_servers.sh
./start_servers.sh
```

## Manual Start

If you prefer to start servers manually:

### Terminal 1 - Backend API
```bash
uvicorn backend.api:app --reload --port 8000
```

### Terminal 2 - Fatigue Detection Server
```bash
# Windows PowerShell:
$env:FATIGUE_PORT=8001; python fatigue_detection/app.py

# Windows CMD:
set FATIGUE_PORT=8001 && python fatigue_detection/app.py

# Linux/Mac:
FATIGUE_PORT=8001 python fatigue_detection/app.py
```

## Port Configuration

- **Backend API**: Port 8000 (hardcoded in uvicorn command)
- **Fatigue Detection**: Port 8001 (set via `FATIGUE_PORT` environment variable)

To change the fatigue detection port, modify the `FATIGUE_PORT` environment variable:
- Default: 8000 (if not set)
- Recommended: 8001 (to avoid conflict with backend API)

## Troubleshooting

### Port Already in Use
If you get a "port already in use" error:

**Windows:**
```powershell
# Find process using port 8000
netstat -ano | findstr :8000

# Find process using port 8001
netstat -ano | findstr :8001

# Kill process (replace PID with actual process ID)
taskkill /PID <PID> /F
```

**Linux/Mac:**
```bash
# Find process using port
lsof -i :8000
lsof -i :8001

# Kill process
kill -9 <PID>
```

### Camera Access Issues
The fatigue detection server requires exclusive camera access. If you're running calibration (`calibration_cli.py`), stop the fatigue detection server first, or use a different camera index:

```bash
python fatigue_detection/calibration_cli.py --user your_user --camera-index 1
```

## Server URLs

Once both servers are running:
- Backend API: http://localhost:8000
- Fatigue Detection: http://localhost:8001
- API Documentation: http://localhost:8000/docs
- Fatigue Detection WebSocket: ws://localhost:8001/ws/fatigue-detect
