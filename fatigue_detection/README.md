# Fatigue Detection System

Real-time fatigue detection system with C++ core engine, Python daemon server, and personalized calibration profiles.

## Architecture

- **C++ Core Module**: High-performance face detection, landmark tracking, and fatigue metrics calculation
- **Python Daemon**: Owns camera (`cv2.VideoCapture`), processes frames with zero-copy C++ integration
- **WebSocket Server**: Streams lightweight JSON metrics to frontend (no Base64 images)
- **Frontend**: Receives metrics and displays fatigue status, handles PVT challenges

## Key Features

### Passive Detectors
- **Yawning Detection**: Mouth Aspect Ratio (MAR) tracking
- **Gaze/Zoning Out**: Eye saccades and blink rate monitoring
- **Fidgeting**: Motion Energy with relative ROI (tracks torso relative to face position)
- **Neck Cracking**: Head pose velocity detection

### Active Detector
- **PVT Challenge**: Psychomotor Vigilance Task triggered at fatigue_score >= 0.7

### Personalization
- **Baseline Calibration**: 20-minute work session + 5-minute break session
- **Z-Score Fusion**: Sigmoid-clamped Z-scores prevent false positives from outliers
- **Profile-Based Detection**: Personalized thresholds based on user's normal behavior

## Performance Optimizations

1. **Zero-Copy Architecture**: Numpy arrays passed directly to C++ (no WebSocket base64 overhead)
2. **Mandatory Downscaling**: Frames resized to 640x480 before Dlib detection (1080p = 5 FPS, 640x480 = 30+ FPS)
3. **Frame Processing Hierarchy**: 
   - Face detection: Every frame (30/sec)
   - Motion Energy: Every 5th frame (6/sec)
   - Z-score calc: Every 30th frame (1/sec)
4. **Relative ROI**: Torso ROI calculated from face bounding box (tracks with user movement)

## Setup

### Prerequisites

- Python 3.8+
- CMake 3.15+
- C++ compiler with C++17 support
- OpenCV 4.8+
- Dlib (with AVX support)
- Eigen3
- Pybind11
- nlohmann/json (header-only, downloaded by CMake if not found)

### Build C++ Module

**Linux/Mac:**
```bash
cd fatigue_detection/cpp
mkdir build && cd build
cmake ..
make
```

**Windows PowerShell:**
```powershell
cd fatigue_detection/cpp
mkdir build; cd build
cmake ..
cmake --build . --config Release
```

**Windows Command Prompt:**
```cmd
cd fatigue_detection\cpp
mkdir build
cd build
cmake ..
cmake --build . --config Release
```

The module will be built as `lockin_core.so` (Linux/Mac) or `lockin_core.pyd` (Windows) in the `fatigue_detection/` directory.

**Note**: Dlib requires the 68-point landmark predictor model file. Download from:
```
http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
```

Extract and place in `fatigue_detection/models/` or set the path when initializing `FaceEngine`.

### Install Python Dependencies

```bash
pip install -r fatigue_detection/requirements.txt
```

## Running

### Start Daemon Server

```bash
cd fatigue_detection
python app.py
```

The server will:
- Open camera on startup (`cv2.VideoCapture(0)`)
- Start WebSocket server on `ws://127.0.0.1:8000/ws/fatigue-detect`
- Process frames at ~30 FPS
- Send JSON metrics to connected clients

### Frontend Integration

The frontend connects to the WebSocket and receives metrics only (no camera capture needed). The React component (`LockInView.jsx`) displays:
- Fatigue score (0-100%)
- Fatigue level (focused/moderate/high)
- Blink rate, gaze stability, fidgeting score
- Recommendation (continue/take_short_break/take_long_break)
- PVT challenge UI when triggered

### Calibration

Run a calibration session to create a personalized profile:

```bash
python fatigue_detection/calibration.py <user_id>
```

This runs:
1. 20-minute work session (collect baseline metrics)
2. User rates focus (1-10)
3. If rating >= 8: Profile saved as baseline
4. If rating < 5: Data discarded

## API Endpoints

### WebSocket: `/ws/fatigue-detect`

**Client → Server**: None (server owns camera)

**Server → Client**: JSON messages
```json
{
  "type": "metrics",
  "timestamp": 1234567890,
  "data": {
    "blink_rate": 12.5,
    "perclos": 0.25,
    "yawn_count_5min": 2,
    "gaze_stability": 0.85,
    "fidgeting_score": 0.15,
    "neck_crack_count_1min": 0,
    "fatigue_score": 0.45,
    "fatigue_level": "moderate",
    "recommendation": "continue"
  }
}
```

PVT Challenge:
```json
{
  "type": "pvt_challenge",
  "delay_ms": 3000,
  "triggered_by_fatigue_score": 0.75
}
```

### REST: `/api/fatigue/set-user/{user_id}`

Switch to different user profile or initialize camera.

### REST: `/api/fatigue/status`

Get current status (camera initialized, engine initialized, active connections).

### REST: `/api/fatigue/pvt-response`

Handle PVT challenge response:
```json
{
  "reaction_time_ms": 285
}
```

## Performance Benchmarks

- **Frame Processing**: <25ms per frame (including downscaling)
- **Downscaling**: ~1-2ms (640x480 from 1080p)
- **Network**: Only JSON metrics (~1KB per frame = 30KB/sec)
- **CPU Savings**: ~30-50% by removing Base64 encoding/decoding

## Testing

1. **Performance**: Verify frame processing latency <25ms
2. **ROI Validation**: Test relative ROI with face movement
3. **Downscaling**: Confirm Dlib runs at 30+ FPS on 640x480
4. **Calibration**: Test profile generation and loading
5. **PVT Challenge**: Test challenge triggering and response

## Troubleshooting

### Camera Not Opening
- Check camera permissions
- Try different camera index: `/api/fatigue/set-user/<user_id>?camera_index=1`
- Verify camera is not in use by another application

### Module Not Found
- Ensure C++ module is built: `cd fatigue_detection/cpp/build && make`
- Check Python path includes `fatigue_detection/` directory

### Low FPS
- Verify downscaling is working (check logs)
- Ensure Dlib is compiled with AVX support
- Check CPU usage (should be <50% per core)

### Profile Not Loading
- Check profile file exists: `fatigue_detection/profiles/{user_id}.json`
- Verify JSON format is valid
- Run calibration if profile doesn't exist

## Future Enhancements

- Mouse movement tracking (system hooks)
- Keyboard dynamics analysis
- Machine learning model for personalized thresholds
- Firebase sync for profiles (cloud backup)
- ONNX Runtime integration (faster face detection)
