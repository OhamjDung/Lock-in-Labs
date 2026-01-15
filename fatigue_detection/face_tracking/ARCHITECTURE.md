# Hybrid Architecture V2: MediaPipe + C++ Engine

## Overview

This document describes the hybrid architecture that combines Google MediaPipe (Python) for face tracking with the existing C++ fatigue detection engine.

## Problem Statement

The previous C++ implementation using Dlib/YuNet had issues with:
- **Glasses:** Poor detection accuracy
- **Rotation:** Limited head pose handling
- **Jitter:** Unstable landmark tracking

## Solution: Hybrid Architecture

### Vision Layer (Python - MediaPipe)
- **Technology:** Google MediaPipe Face Mesh
- **Responsibilities:**
  - Face detection
  - 468-point landmark extraction
  - EAR (Eye Aspect Ratio) calculation
  - MAR (Mouth Aspect Ratio) calculation
  - Head pose estimation (gaze direction)
- **Advantages:**
  - Excellent glasses handling
  - Robust rotation tracking (up to 90°)
  - Built-in temporal filtering (reduces jitter)
  - Simple installation (`pip install mediapipe`)
  - High performance (30+ FPS on CPU)

### Logic Layer (C++ - Fatigue Engine)
- **Technology:** Existing C++ module (`lockin_core`)
- **Responsibilities:**
  - Z-score calculations
  - Baseline comparisons
  - Fatigue score computation
  - Profile management
  - Blink rate, PERCLOS, gaze stability metrics
- **Advantages:**
  - Fast mathematical computations
  - Existing calibration system
  - Profile persistence

## Data Flow

```
Camera Frame
    ↓
MediaPipe Vision System (Python)
    ├─→ Face Detection
    ├─→ Landmark Extraction (468 points)
    ├─→ EAR Calculation
    ├─→ MAR Calculation
    └─→ Gaze Estimation
    ↓
Metrics Dictionary
    {
        "ear": float,
        "mar": float,
        "gaze_x": float,
        "gaze_y": float,
        "face_detected": bool
    }
    ↓
C++ Fatigue Engine
    ├─→ Update Statistics
    ├─→ Calculate Z-scores
    ├─→ Compute Fatigue Score
    └─→ Generate Alerts
    ↓
Fatigue Metrics
    {
        "fatigue_score": float,
        "fatigue_level": str,
        "blink_rate": float,
        "perclos": float,
        ...
    }
```

## Current Implementation Status

### ✅ Completed
- [x] MediaPipe Vision System (`vision_system.py`)
- [x] EAR/MAR calculation from MediaPipe landmarks
- [x] Head pose estimation (gaze direction)
- [x] Face bounding box calculation
- [x] Test script (`test_vision.py`)
- [x] Integration example (`integration_example.py`)

### 🔄 Next Steps (C++ Integration)

To fully integrate MediaPipe with the C++ engine, we need to:

1. **Add C++ method to accept metrics directly:**
   ```cpp
   // In detector.h
   StateVector update_metrics(
       double ear,
       double mar,
       double gaze_x,
       double gaze_y,
       int64_t timestamp_ms
   );
   ```

2. **Update Python wrapper (`engine.py`):**
   ```python
   def update_metrics(self, ear, mar, gaze_x, gaze_y, timestamp_ms):
       return self._engine.update_metrics(ear, mar, gaze_x, gaze_y, timestamp_ms)
   ```

3. **Modify `app.py` to use MediaPipe:**
   - Replace `engine.process_frame(frame)` with:
     ```python
     vision_results = vision_system.process(frame)
     if vision_results["face_detected"]:
         metrics = engine.update_metrics(
             ear=vision_results["ear"],
             mar=vision_results["mar"],
             gaze_x=vision_results["gaze_x"],
             gaze_y=vision_results["gaze_y"],
             timestamp_ms=timestamp_ms
         )
     ```

## Benefits

1. **Stability:** MediaPipe's temporal filtering eliminates jitter
2. **Accuracy:** Better face detection with glasses and rotation
3. **Simplicity:** No complex C++ build system for face detection
4. **Performance:** MediaPipe is highly optimized (C++ under the hood)
5. **Maintainability:** Clear separation of concerns

## Testing

1. **Test MediaPipe alone:**
   ```bash
   python fatigue_detection/face_tracking/test_vision.py
   ```

2. **Test integration (current - still uses C++ Dlib):**
   ```bash
   python fatigue_detection/face_tracking/integration_example.py
   ```

3. **Full integration (after C++ updates):**
   - Update `app.py` to use MediaPipe vision system
   - Test with calibration and fatigue detection

## Installation

```bash
# Install MediaPipe
pip install mediapipe

# Or install all requirements
pip install -r requirements.txt
```

## Performance Expectations

- **MediaPipe Processing:** ~30-60 FPS (CPU)
- **C++ Engine Processing:** <1ms per frame
- **Total Pipeline:** ~30-60 FPS (bottleneck is MediaPipe)

## Future Enhancements

1. **Iris Tracking:** MediaPipe's `refine_landmarks=True` enables iris tracking for better gaze estimation
2. **Multi-face Support:** Currently limited to 1 face, can be extended
3. **3D Head Pose:** MediaPipe provides 3D coordinates for more accurate pose estimation
4. **Custom Landmark Selection:** Optimize landmark indices for specific use cases
