# Fatigue Detection Metrics Explained

## Core Metrics

### 1. **Blink Rate** (blinks/min)
- **What it measures**: How many times you blink per minute
- **Normal range**: 15-20 blinks/min when alert
- **Fatigue indicator**: 
  - Too low (<10/min) = Zoning out or very tired
  - Too high (>30/min) = Eye strain or dry eyes
- **How it works**: Uses Eye Aspect Ratio (EAR) - measures vertical vs horizontal eye opening

### 2. **PERCLOS** (Percentage of Eyelid Closure)
- **What it measures**: What percentage of time your eyes are closed (0.0 = always open, 1.0 = always closed)
- **Normal range**: 0.0-0.1 (eyes open 90-100% of time)
- **Fatigue indicator**: 
  - >0.2 = Getting drowsy (eyes closed 20%+ of time)
  - >0.5 = Very tired (eyes closed 50%+ of time)
- **How it works**: Tracks EAR over time, calculates percentage below threshold

### 3. **Gaze Stability** (0.0-1.0)
- **What it measures**: How stable your gaze is (1.0 = perfectly still, 0.0 = very jittery)
- **Normal range**: 0.7-1.0 when focused
- **Fatigue indicator**:
  - High (>0.95) + Low blink rate = "Zoning out" (staring blankly)
  - Low (<0.5) = Eyes moving erratically (tired, unfocused)
- **How it works**: Calculates variance of eye center position over time

### 4. **Fidget Score** (0.0-1.0)
- **What it measures**: How much you're moving your torso/shoulders
- **Normal range**: 0.0-0.3 when sitting still
- **Fatigue indicator**:
  - High (>0.5) = Restless, fidgeting (anxiety or need to move)
  - Very low (<0.1) = Too still (might be zoning out)
- **How it works**: Motion energy detection in torso region (relative to face position)

### 5. **Yawn Count** (count/5min)
- **What it measures**: Number of yawns in the last 5 minutes
- **Normal range**: 0-1 yawns/5min
- **Fatigue indicator**:
  - 1 yawn = Normal (oxygen regulation)
  - 3+ yawns/5min = Fatigue event (body needs rest)
- **How it works**: Mouth Aspect Ratio (MAR) - detects when mouth opens wide for >2 seconds

### 6. **Neck Crack Count** (count/1min)
- **What it measures**: Rapid head rotations (tension release)
- **Normal range**: 0-1/min
- **Fatigue indicator**:
  - Frequent cracking = Physical discomfort (ergonomics issue or stress)
- **How it works**: Detects sudden high-velocity head rotations

### 7. **Fatigue Score** (0.0-1.0) ⭐ MAIN METRIC
- **What it measures**: Overall fatigue level (0.0 = alert, 1.0 = very tired)
- **How it's calculated**: Weighted fusion of all metrics using Z-scores vs your personal baseline
- **Interpretation**:
  - 0.0-0.3 = **Focused** (green) - Keep working
  - 0.3-0.7 = **Moderate** (yellow) - Take a short break soon
  - 0.7-1.0 = **High** (red) - Take a break now, PVT challenge triggered

### 8. **Fatigue Level** (text)
- **Values**: "focused", "moderate", "high"
- **Based on**: Fatigue score thresholds

### 9. **Recommendation** (text)
- **Values**: 
  - "continue" - Keep working
  - "take_short_break" - 5-10 min break recommended
  - "take_long_break" - 15+ min break needed

## Z-Scores (Internal)

These are used internally to calculate fatigue score:
- **z_score_blink**: How many standard deviations your blink rate is from baseline
- **z_score_gaze**: Deviation in gaze stability
- **z_score_posture**: Deviation in head position
- **z_score_fidget**: Deviation in fidgeting

All Z-scores are clamped with sigmoid (tanh) to prevent extreme outliers.

## Why Calibration Matters

Everyone has different:
- Eye shapes (affects EAR threshold)
- Blink rates (some people blink more/less naturally)
- Movement patterns (some fidget more, some sit still)
- Head positions (some lean forward, some back)

**Without calibration**: System uses generic thresholds → false positives
**With calibration**: System learns YOUR baseline → accurate detection
