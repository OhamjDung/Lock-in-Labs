# Face Tracking System (MediaPipe)

This module replaces the C++ Dlib/YuNet face detection code with Google MediaPipe Face Mesh for better stability, especially with glasses and head rotation.

## Architecture

**Hybrid Architecture V2:**
- **Vision Layer (Python):** MediaPipe Face Mesh processes camera frames and extracts landmarks/metrics
- **Logic Layer (C++):** Existing C++ module handles Z-scores, profiles, and fatigue calculations

## Why MediaPipe?

1. **Glasses:** Handles them perfectly (trained on diverse datasets)
2. **Rotation:** Tracks up to 90 degrees reliably
3. **Jitter:** Rock solid (uses temporal filtering built-in)
4. **Integration:** Simple `pip install mediapipe` - no complex build system

## Installation

```bash
pip install mediapipe
```

## Usage

```python
from fatigue_detection.face_tracking import VisionSystem
import cv2

# Initialize vision system
vision = VisionSystem(
    max_num_faces=1,
    refine_landmarks=True,  # Enable iris tracking for better gaze
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5
)

# Process frames
cap = cv2.VideoCapture(0)
while True:
    ret, frame = cap.read()
    if not ret:
        break
    
    # Process frame
    results = vision.process(frame)
    
    if results["face_detected"]:
        print(f"EAR: {results['ear']:.3f}, MAR: {results['mar']:.3f}")
        
        # Optional: Draw landmarks for debugging
        frame = vision.draw_landmarks(frame, results)
    
    cv2.imshow("Face Tracking", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

vision.release()
cap.release()
```

## Metrics Extracted

- **EAR (Eye Aspect Ratio):** Average of left and right eye, plus individual values
- **MAR (Mouth Aspect Ratio):** Mouth openness metric
- **Gaze (X, Y):** Head pose estimation (yaw and pitch, normalized -0.5 to 0.5)
- **Face Bounding Box:** (x, y, width, height)

## Integration with C++ Engine

The vision system extracts metrics in Python, then sends them to the C++ engine for:
- Z-score calculations
- Baseline comparisons
- Fatigue score computation
- Profile management

This separation allows us to leverage MediaPipe's stability while keeping the performance-critical math in C++.
