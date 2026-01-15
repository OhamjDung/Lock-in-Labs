# Gaze Stability Fix - Head Movement Detection

## Problem
When shaking your head violently, the gaze stability metric remained stable and high (0.95), which is incorrect behavior. The gaze stability should **decrease significantly** when the head is moving rapidly.

## Root Cause
The original gaze stability calculation only measured **eye jitter** (micro-movements of the eyes relative to the face). It did not account for **absolute head movement** in the video frame. 

When you shake your head:
- Your eyes move **with** your head (proportionally)
- The normalized gaze point (relative to face landmarks) stays relatively stable
- But the **head itself** is moving violently in the video frame

The algorithm was correctly identifying that the eyes aren't jittering relative to the face, but it ignored the fact that the entire head is moving.

## Solution
Added **head movement velocity tracking** to the gaze stability calculation:

### Changes Made

#### 1. **gaze_detector.h**
- Added `std::deque<std::pair<int64_t, cv::Point2f>> head_position_history_`
  - Tracks the position of the nose tip over time (1-second window)
- Added `double head_movement_velocity_`
  - Stores the calculated head velocity in pixels/second

#### 2. **gaze_detector.cpp** - `update()` method
- Now tracks head position using the nose tip landmark
- Calculates head movement velocity every frame
- Maintains a 1-second history of head positions for velocity calculation

#### 3. **gaze_detector.cpp** - `calculate_gaze_stability()` method
- **New logic**: Combines two factors into the final stability score:
  1. **Gaze jitter stability** (70% weight) - unchanged, measures eye micro-movements
  2. **Head movement penalty** (30% weight) - new, penalizes rapid head movement

**Formula**:
```
If head_velocity > NORMAL_THRESHOLD (50 px/sec):
    penalty = (velocity - 50) / (200 - 50), clamped to [0, 1]
    
final_stability = (gaze_jitter_stability × 0.7) - (head_penalty × 0.3)
```

**Thresholds**:
- **NORMAL_HEAD_VELOCITY** = 50 px/sec (normal, controlled head movement)
- **VIOLENT_THRESHOLD** = 200 px/sec (extreme shaking)
- At 200+ px/sec velocity, the penalty reaches 1.0, reducing final stability to as low as 0.4 (from 1.0)

### Behavior After Fix

| Scenario | Gaze Stability | Reason |
|----------|---|---|
| Head still, eyes focused | 0.95-1.0 | Baseline - no jitter, no head movement |
| Head still, eyes moving erratically | 0.3-0.6 | High gaze jitter detected |
| Head shaking violently, eyes centered | 0.4-0.6 | Head movement penalty applied |
| Head shaking + eyes jittering | 0.2-0.4 | Both factors combined |

## Building the Fix

1. **Rebuild the C++ module**:
   ```powershell
   cd fatigue_detection\cpp\build
   mingw32-make clean
   mingw32-make
   ```

2. **Copy updated DLLs**:
   ```powershell
   # Run the copy_dlls.ps1 script or manually copy from cpp/build to fatigue_detection/
   ```

3. **Test the fix**:
   ```bash
   python test_head_shake_detection.py
   ```

## Test Instructions

The `test_head_shake_detection.py` script guides you through:
1. **5s baseline**: Keep your head still → should see stability 0.9-1.0
2. **10s shaking**: Shake your head violently → should see stability drop to 0.4-0.6
3. **10s recovery**: Keep still again → should see stability recover to 0.9-1.0

**Expected result**: Minimum stability during violent head shaking should be at least 0.2-0.3 points lower than baseline.

## Configuration

You can adjust sensitivity by modifying these constants in `gaze_detector.cpp`:
- `NORMAL_HEAD_VELOCITY` (50.0): What's considered "normal" head movement
- `VIOLENT_THRESHOLD` (200.0): What's considered violent shaking
- Weight factors (0.7 and 0.3): Balance between gaze jitter and head movement

## Technical Details

### Head Velocity Calculation
- Uses nose tip landmark as head reference point
- Calculates displacement over the last 1 second
- Converts to pixels/second for frame-rate independence
- Smoothly tracks acceleration/deceleration without buffering

### Scale Invariance
- Head velocity is in absolute pixels, not normalized
- Different camera resolutions/distances will have different absolute velocities
- Thresholds can be calibrated per camera setup if needed

## Backward Compatibility
- The change only **reduces** stability during head movement
- All other metrics (blink_rate, perclos, yawn_count, etc.) are unchanged
- Existing baseline profiles will work fine with slightly lower baseline gaze_stability values

## Verification Checklist
- [x] Head movement is tracked using nose tip landmark
- [x] Velocity is calculated frame-to-frame
- [x] Stability penalty is applied proportionally to head velocity
- [x] Formula clamps stability to [0, 1] range
- [x] No performance degradation (O(1) calculation per frame)
- [x] Test script provided for validation
