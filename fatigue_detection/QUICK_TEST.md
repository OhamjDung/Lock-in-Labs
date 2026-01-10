# Quick Test Instructions

## Fixed Issues

1. ✅ **Dictionary vs Object**: Fixed `engine.py` to handle C++ module returning dict directly
2. ✅ **WebSocket setup**: Server accepts WebSocket connections properly
3. ✅ **Python path**: Using system Python explicitly

## To Test Now

### Step 1: Start Server (Terminal 1)

```powershell
cd "D:\Noobcept\Lock In Labs"
C:\Users\ohamj\AppData\Local\Programs\Python\Python313\python.exe fatigue_detection/app.py
```

Wait for:
```
[INFO] Camera and engine initialized successfully
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Step 2: Run Test (Terminal 2)

```powershell
cd "D:\Noobcept\Lock In Labs"
C:\Users\ohamj\AppData\Local\Programs\Python\Python313\python.exe fatigue_detection/test_websocket.py
```

### What to Expect

- ✅ Connected to WebSocket
- Real-time metrics scrolling:
  ```
  [14:32:15.123] Frame #1 | Face: ✓ | Fatigue: 0.15 | Blink: 12.5/min | Yawns: 0 | Fidget: 0.03
  ```

### Troubleshooting

**"Connection refused"**:
- Make sure server started in Terminal 1
- Check: `netstat -ano | findstr :8000`

**"Processing error"**:
- Fixed! The dict issue is resolved in `engine.py`

**No face detection**:
- Sit in front of camera
- Make sure camera is working

## What Changed

`engine.py` now properly handles C++ module returning a dict:
- Checks if result is already a dict (it is)
- Adds `face_detected` flag
- Adds backwards-compatible aliases (`yawn_count`, `fidget_score`)
