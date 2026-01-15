#!/bin/bash
# Start Both Servers Script (Linux/Mac)
# Starts backend API on port 8000 and fatigue detection server on port 8001

echo "========================================"
echo "Starting Lock In Labs Servers"
echo "========================================"
echo ""

# Get the script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# Start Backend API on port 8000 in background
echo "[1/2] Starting Backend API on port 8000..."
gnome-terminal -- bash -c "cd '$SCRIPT_DIR' && echo 'Backend API Server (Port 8000)' && echo 'Press CTRL+C to stop' && uvicorn backend.api:app --reload --port 8000; exec bash" 2>/dev/null || \
xterm -e "cd '$SCRIPT_DIR' && echo 'Backend API Server (Port 8000)' && echo 'Press CTRL+C to stop' && uvicorn backend.api:app --reload --port 8000; exec bash" 2>/dev/null || \
osascript -e "tell app \"Terminal\" to do script \"cd '$SCRIPT_DIR' && echo 'Backend API Server (Port 8000)' && echo 'Press CTRL+C to stop' && uvicorn backend.api:app --reload --port 8000\"" 2>/dev/null || \
{
    echo "Could not open new terminal. Starting in background..."
    uvicorn backend.api:app --reload --port 8000 &
    BACKEND_PID=$!
}

# Wait a moment for the first server to start
sleep 3

# Start Fatigue Detection Server on port 8001
echo "[2/2] Starting Fatigue Detection Server on port 8001..."
export FATIGUE_PORT=8001
python fatigue_detection/app.py

echo ""
echo "========================================"
echo "Servers Started:"
echo "  Backend API:        http://localhost:8000"
echo "  Fatigue Detection:  http://localhost:8001"
echo "========================================"
