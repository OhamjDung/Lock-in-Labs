# Camera Screen Explanation - Everything You See

This document explains every word, metric, and visual element that appears on the fatigue detection camera window.

---

## Top Section (Left Side Panel)

### 1. **"FATIGUE DETECTION"** (Title)
- **What it is**: The main title of the application
- **Color**: White
- **Purpose**: Identifies the application window

---

### 2. **"FACE: DETECTED"** or **"FACE: NOT DETECTED"**
- **What it means**: 
  - **"FACE: DETECTED"** (Green) = Your face is being tracked by the camera
  - **"FACE: NOT DETECTED"** (Red) = Camera can't see/find your face
- **When to worry**: If it stays red, move closer to camera or ensure good lighting
- **Color coding**: 
  - 🟢 Green = Face found
  - 🔴 Red = Face not found

---

### 3. **"FATIGUE: X.XX"** (Main Score)
- **What it measures**: Overall fatigue level on a scale of 0.00 to 1.00
- **What the numbers mean**:
  - **0.00 - 0.30** = 🟢 **Focused** (You're alert, keep working)
  - **0.30 - 0.70** = 🟡 **Moderate** (Getting tired, break soon)
  - **0.70 - 1.00** = 🔴 **High** (Very tired, take a break now!)
- **How it's calculated**: Combines all other metrics (blinks, yawns, gaze, etc.) into one score
- **Color coding**: Changes from green → orange → red as fatigue increases

---

### 4. **"LEVEL: FOCUSED/MODERATE/HIGH"**
- **What it means**: Text version of your fatigue score
  - **"FOCUSED"** = Low fatigue (green)
  - **"MODERATE"** = Medium fatigue (orange/yellow)
  - **"HIGH"** = High fatigue (red)
- **Purpose**: Quick, easy-to-read status

---

### 5. **"Blink Rate: XX.X/min"**
- **What it measures**: How many times you blink per minute
- **Normal range**: 15-20 blinks/min when alert
- **What the numbers mean**:
  - **< 10/min** = Too low (zoning out or very tired)
  - **15-20/min** = Normal (healthy alert state)
  - **> 30/min** = Too high (eye strain, dry eyes, or anxiety)
- **Why it matters**: Blink rate drops when tired or zoning out

---

### 6. **"Blink Count: XXX"**
- **What it measures**: Total number of blinks detected since the session started
- **Purpose**: 
  - Helps verify blink detection is working
  - Shows cumulative progress
  - Should increase as you blink normally
- **If it's stuck at 0**: Blink detection might not be working (try calibrating with 'C' key)

---

### 7. **"Eye Closure: X.X%"** (PERCLOS)
- **What it measures**: Percentage of time your eyes are closed (0% = always open, 100% = always closed)
- **What the numbers mean**:
  - **0-10%** = 🟢 Normal (eyes open 90-100% of time)
  - **10-20%** = 🟡 Getting drowsy
  - **20-50%** = 🟠 Tired (eyes closed 20-50% of time)
  - **> 50%** = 🔴 Very tired (eyes closed more than half the time)
- **Why it matters**: Drowsy people keep their eyes closed longer

---

### 8. **"EAR: X.XXX (OPEN/CLOSED) [Th: X.XX]"**
- **What it measures**: **Eye Aspect Ratio** - the current measurement of your eye opening
- **Formula**: `EAR = (average vertical eye opening) / (horizontal eye width)`
- **What the numbers mean**:
  - **EAR value** (first number): Current eye opening measurement
    - Typically **0.25-0.40** when eyes are open
    - Drops to **< 0.20** when eyes are closed
  - **(OPEN/CLOSED)**: Current status based on threshold
  - **[Th: X.XX]**: Your personal threshold (set via calibration)
- **Color coding**:
  - 🟢 Green = Eyes open (EAR > threshold)
  - 🟡 Yellow = Eyes closed (EAR < threshold)
- **When to calibrate**: If it shows "CLOSED" when your eyes are open, press 'C' to calibrate

---

### 9. **"MAR: X.XXX (OPEN/CLOSED) [Th: X.XX]"**
- **What it measures**: **Mouth Aspect Ratio** - the current measurement of your mouth opening
- **Formula**: `MAR = (average vertical mouth opening) / (horizontal mouth width)`
- **What the numbers mean**:
  - **MAR value** (first number): Current mouth opening measurement
    - Typically **0.20-0.35** when mouth is closed
    - Increases to **0.50+** when mouth is wide open (yawning)
  - **(OPEN/CLOSED)**: Current status based on threshold
  - **[Th: X.XX]**: Your personal threshold (set via calibration)
- **When to calibrate**: If yawns aren't detected, press 'Y' while yawning to calibrate

---

### 10. **"✓ EAR calibrated: X.XXX"** or **"✓ MAR calibrated: X.XXX"** (Temporary Message)
- **What it means**: Confirmation that calibration was successful
- **When it appears**: For 3 seconds after pressing 'C' or 'Y'
- **Purpose**: Confirms your threshold was updated

---

### 11. **"Yawns (5min): X"**
- **What it measures**: Number of yawns detected in the last 5 minutes
- **What the numbers mean**:
  - **0-1** = Normal (occasional yawning is healthy)
  - **2-3** = Getting tired
  - **3+** = 🔴 Fatigue event (your body needs rest)
- **Why it matters**: Frequent yawning indicates fatigue or lack of oxygen

---

### 12. **"Gaze Stability: X.XX"**
- **What it measures**: How still your eyes are looking (0.00 = very jittery, 1.00 = perfectly still)
- **What the numbers mean**:
  - **0.70-1.00** = 🟢 Good (eyes stable, focused)
  - **0.40-0.70** = 🟡 Moderate (eyes moving around some)
  - **< 0.40** = 🔴 Poor (eyes moving erratically, unfocused)
- **Special cases**:
  - **Very high (>0.95) + Low blink rate** = "Zoning out" (staring blankly)
  - **Very low (<0.5)** = Eyes jumping around (tired or distracted)
- **How it's calculated**: Measures how much your eye center position moves over time

---

### 13. **"Fidget Score: X.XX"**
- **What it measures**: How much you're moving your torso/shoulders (0.00 = still, 1.00 = very restless)
- **What the numbers mean**:
  - **0.00-0.30** = 🟢 Normal (sitting still, focused)
  - **0.30-0.50** = 🟡 Some movement (slight restlessness)
  - **0.50-0.70** = 🟠 Restless (fidgeting, anxiety)
  - **> 0.70** = 🔴 Very restless (high anxiety or need to move)
- **Why it matters**: High fidgeting can indicate anxiety or discomfort (needs a walk, not a nap)

---

### 14. **"Neck Cracks: X"** (Only shown if > 0)
- **What it measures**: Number of rapid head rotations in the last 1 minute
- **What the numbers mean**:
  - **0** = Normal (not shown)
  - **1-2** = Some neck tension
  - **3+** = 🟡 Frequent cracking (ergonomics issue or stress)
- **Why it matters**: Frequent neck cracking indicates physical discomfort or tension

---

### 15. **"REC: CONTINUE"** or **"REC: TAKE SHORT BREAK"** or **"REC: TAKE LONG BREAK"**
- **What it means**: System recommendation based on your fatigue score
- **Options**:
  - **"CONTINUE"** = 🟢 Keep working, you're doing fine
  - **"TAKE SHORT BREAK"** = 🟡 Take 5-10 minute break soon
  - **"TAKE LONG BREAK"** = 🔴 Take 15+ minute break now
- **Color coding**: Green for continue, orange/yellow for breaks

---

## Bottom Section (Instructions)

### 16. **"CALIBRATION:"**
- **What it means**: Section header for calibration instructions

### 17. **"Press 'C' when eyes CLOSED"**
- **What it means**: Instructions to calibrate blink detection
- **How to use**: 
  1. Close your eyes completely
  2. Press the 'C' key
  3. System sets your personal EAR threshold

### 18. **"Press 'Y' when YAWNING"**
- **What it means**: Instructions to calibrate yawn detection
- **How to use**: 
  1. Yawn (mouth wide open)
  2. Press the 'Y' key
  3. System sets your personal MAR threshold

---

## Visual Overlays on Camera Feed

### Green Rectangle - **"FACE"**
- **What it is**: Face bounding box
- **Meaning**: Shows the detected face region
- **If missing**: Face not detected (move closer to camera)

---

### Blue Dots and Lines - **"LEFT EYE"** and **"RIGHT EYE"**
- **What it is**: Eye landmark points (6 points per eye)
- **Meaning**: Shows exactly where your eyes are being tracked
- **Purpose**: Visual confirmation that eye tracking is working
- **If missing**: Eye landmarks not detected (face might be at wrong angle)

---

### Yellow Dots and Lines - **"MOUTH"**
- **What it is**: Mouth landmark points (20 points)
- **Meaning**: Shows your mouth outline being tracked
- **Purpose**: Visual confirmation that yawn detection can work
- **If missing**: Mouth landmarks not detected

---

### Yellow Circle - **"NOSE"**
- **What it is**: Nose tip landmark (point 30)
- **Meaning**: Reference point for head pose calculation
- **Purpose**: Used for neck crack detection and head rotation tracking

---

### Orange Rectangle - **"TORSO/SHOULDER ROI"**
- **What it is**: Region of Interest (ROI) for fidget detection
- **Meaning**: Shows the area being monitored for torso/shoulder movement
- **Purpose**: Motion in this region contributes to fidget score
- **If missing**: Face not detected, so ROI can't be calculated

---

### Right Side Status Indicators

### **"FACE DETECTED"** (Green, top-right) or **"NO FACE"** (Red)
- **What it means**: Quick status indicator
- **Purpose**: Immediate visual feedback on detection status

---

## Color Legend

- 🟢 **Green**: Good/Normal state
- 🟡 **Yellow/Orange**: Warning/Moderate state  
- 🔴 **Red**: Alert/Problem state
- ⚪ **White**: Information/Neutral

---

## Quick Troubleshooting

| Problem | What to Check |
|---------|---------------|
| Blink count not increasing | Press 'C' when eyes closed to calibrate |
| Yawns not detected | Press 'Y' when yawning to calibrate |
| Face not detected | Move closer, ensure good lighting, face camera directly |
| EAR always shows "CLOSED" | Calibrate with 'C' key when eyes are actually open |
| All metrics at 0 | Face not detected - check face detection status |

---

## Understanding the Flow

1. **Face Detection** → System finds your face
2. **Landmark Tracking** → Tracks eyes, mouth, nose positions
3. **Metrics Calculation** → Calculates EAR, MAR, gaze, fidget, etc.
4. **Fatigue Fusion** → Combines all metrics into fatigue score
5. **Recommendation** → Suggests action based on fatigue level

---

**Remember**: Press 'C' to calibrate eyes, 'Y' to calibrate yawn detection if metrics seem inaccurate!
