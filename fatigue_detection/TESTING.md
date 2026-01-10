# Testing the Fatigue Detection System

## Quick Test

### Step 1: Start the Daemon

In one terminal, start the server:

```powershell
cd "D:\Noobcept\Lock In Labs"
python fatigue_detection/app.py
```

You should see:
```
[INFO] Starting fatigue detection daemon on http://127.0.0.1:8000
[INFO] Camera will be opened on startup
[INFO] Initializing camera and engine for user: default_user
[INFO] Camera and engine initialized successfully
```

### Step 2: Run the Test Script

In another terminal (keep the first one running), run:

```powershell
cd "D:\Noobcept\Lock In Labs"
python fatigue_detection/test_websocket.py
```

You should see:
- Connection confirmation
- Real-time metrics scrolling (fatigue score, blink rate, yawns, etc.)
- Face detection status (✓ or ✗)

### Step 3: Test Different Behaviors

**Test Yawning:**
- Yawn deliberately a few times
- Watch `Yawns:` counter increase

**Test Fatigue Detection:**
- Close your eyes for a few seconds
- Move around restlessly (fidgeting)
- Fatigue score should increase

**Test PVT Challenge:**
- When fatigue score reaches 0.7 (70%), a PVT challenge should trigger
- You'll see: `🎯 PVT CHALLENGE TRIGGERED!`

**Test Face Detection:**
- Move out of camera view → `Face: ✗`
- Return to camera → `Face: ✓`

## Expected Output

```
============================================================
Fatigue Detection WebSocket Test
============================================================
Connecting to: ws://127.0.0.1:8000/ws/fatigue-detect
Make sure app.py is running in another terminal!
Press Ctrl+C to stop

✅ Connected to WebSocket!

Waiting for metrics... (make sure you're in front of the camera)

------------------------------------------------------------
[14:32:15.123] Frame #1 | Face: ✓ | Fatigue: 0.15 | Blink: 12.5/min | Yawns: 0 | Fidget: 0.03
[14:32:15.156] Frame #2 | Face: ✓ | Fatigue: 0.18 | Blink: 12.5/min | Yawns: 0 | Fidget: 0.04
[14:32:15.189] Frame #3 | Face: ✓ | Fatigue: 0.22 | Blink: 12.5/min | Yawns: 1 | Fidget: 0.05

⚠️  HIGH FATIGUE ALERT! (Score: 0.72)

🎯 PVT CHALLENGE TRIGGERED!
   Fatigue score: 0.72
   Challenge will appear in 3.5 seconds
   (Press spacebar when you see the prompt)
```

## Troubleshooting

### "Connection refused"
- Make sure `app.py` is running in another terminal
- Check if port 8000 is available: `netstat -ano | findstr :8000`

### "Camera not initialized"
- Check if camera opened successfully in `app.py` logs
- Try a different camera index: `/api/fatigue/set-user/default_user?camera_index=1`

### No face detection
- Make sure you're sitting in front of the camera
- Check camera is working: `python -c "import cv2; cap = cv2.VideoCapture(0); print('Camera OK' if cap.isOpened() else 'Camera failed'); cap.release()"`

### Metrics stuck at 0
- Camera might not be capturing frames
- Check `app.py` logs for errors
- Verify C++ module loaded: `python -c "from fatigue_detection.engine import FatigueEngine; print('Engine OK')"`

## Manual API Testing

### Check Status
```powershell
python -c "import urllib.request, json; r = urllib.request.urlopen('http://127.0.0.1:8000/api/fatigue/status'); print(json.dumps(json.loads(r.read()), indent=2))"
```

Should return:
```json
{
  "camera_initialized": true,
  "engine_initialized": true,
  "active_connections": 1
}
```

## Next Steps

Once testing is successful:
1. ✅ Metrics are flowing
2. ✅ Face detection works
3. ✅ Fatigue score updates
4. ✅ PVT challenge triggers

You're ready to integrate with the React frontend!
