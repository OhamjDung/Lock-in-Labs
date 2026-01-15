# Training/Calibration Guide

## Overview

The training mode (`calibration_cli.py`) collects your personalized baseline statistics through a two-phase process:
1. **Work Phase** (30 minutes default): You work normally while the system records your "Lock-In" signature
2. **Break Phase** (5 minutes default): You relax while the system records your "Natural Chaos" signature

## Prerequisites

- **Stop the fatigue detection server** (`app.py`) if it's running, OR use a different camera index
- Good lighting and face the camera
- Be ready to work for the full duration

## Running Training

### Step 1: Stop Fatigue Detection Server (if running)

If you started the servers with `start_servers.ps1`, stop the fatigue detection server:
- Find the terminal window running `fatigue_detection/app.py`
- Press `CTRL+C` to stop it

**OR** use a different camera (see Option 2 below)

### Step 2: Run Calibration

**Basic usage (30 min work, 5 min break):**
```bash
python fatigue_detection/calibration_cli.py --user your_user_id
```

**Custom duration:**
```bash
python fatigue_detection/calibration_cli.py --user your_user_id --work-duration 20 --break-duration 5
```

**If fatigue detection server is still running (use different camera):**
```bash
python fatigue_detection/calibration_cli.py --user your_user_id --camera-index 1
```

## Training Process

1. **Phase 1: Work Session**
   - Camera window opens showing "PHASE 1: LOCK IN"
   - Work normally on a task for the specified duration
   - System collects baseline metrics (blink rate, gaze stability, etc.)
   - Progress shown with time remaining

2. **Rating Prompt**
   - After work phase completes, you'll be asked: "Rate your focus level (1-10)"
   - **Rating >= 8**: High quality, saved as "Golden Standard"
   - **Rating 5-7**: Moderate quality, saved with lower weight
   - **Rating < 5**: Too low, session discarded

3. **Phase 2: Break Session** (only if rating >= 5)
   - Camera window shows "PHASE 2: RELAX"
   - Take a break: check phone, stretch, browse YouTube
   - System collects "chaos" signature for comparison
   - Duration: 5 minutes (default)

4. **Save Profile**
   - Statistics are calculated and saved to your profile
   - Profile saved to: `fatigue_detection/profiles/your_user_id.json`
   - You can now restart the fatigue detection server

## After Training

1. **Restart Fatigue Detection Server:**
   ```bash
   # Option 1: Use startup script
   .\start_servers.ps1
   
   # Option 2: Manual start
   $env:FATIGUE_PORT=8001; python fatigue_detection/app.py
   ```

2. **The server will now use your personalized baseline** for fatigue detection

## Command Line Options

```bash
python fatigue_detection/calibration_cli.py [OPTIONS]

Options:
  --user USER_ID           User identifier (default: default_user)
  --work-duration MINUTES  Work phase duration in minutes (default: 30)
  --break-duration MINUTES Break phase duration in minutes (default: 5)
  --camera-index INDEX     Camera device index (default: 0)
                          Use 1, 2, etc. if camera 0 is in use
```

## Examples

**Quick test (1 minute work, 30 seconds break):**
```bash
python fatigue_detection/calibration_cli.py --user test_user --work-duration 1 --break-duration 1
```

**Full 30-minute training:**
```bash
python fatigue_detection/calibration_cli.py --user tom_pham --work-duration 30 --break-duration 5
```

**Training while fatigue server is running (different camera):**
```bash
python fatigue_detection/calibration_cli.py --user tom_pham --camera-index 1
```

## Troubleshooting

### "Failed to open camera"
- Make sure no other application is using the camera
- Stop the fatigue detection server if it's running
- Try a different camera index: `--camera-index 1`

### "Very few frames with face detected"
- Improve lighting
- Move closer to camera
- Ensure face is clearly visible

### Training interrupted
- Press 'q' in the camera window to abort
- You can restart training anytime
