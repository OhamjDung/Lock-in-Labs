# Desktop Notifications Guide

## Overview

The fatigue detection system now includes desktop notifications (Windows toast notifications) that alert you when:

1. **Not Locked In** - You're deviating from your personalized baseline (distracted)
2. **Fatigue Detected** - Your fatigue score exceeds thresholds
3. **Break Needed** - The system recommends taking a break

## How It Works

### 1. "Not Locked In" Detection

**Trigger:** When your Z-scores deviate significantly from your baseline
- **Z-score threshold:** 0.7 (70% deviation from baseline)
- **Cooldown:** 60 seconds between notifications
- **What it detects:**
  - High fidgeting (unusual movement patterns)
  - Gaze instability (looking around, not focused)
  - Unusual blink patterns
  - General behavior deviation

**Notification:**
- Title: "🔓 Not Locked In"
- Message: Explains what's causing the deviation (e.g., "High fidgeting detected")

### 2. Fatigue Detection

**Triggers:**
- **Warning (Moderate):** Fatigue score >= 0.5
  - Title: "💤 Fatigue Warning"
  - Message: "Moderate fatigue detected. You may want to take a short break soon."
  - Cooldown: 120 seconds

- **Critical (High):** Fatigue score >= 0.7
  - Title: "⚠️ High Fatigue Detected"
  - Message: Varies based on energy type:
    - **Sleepy:** "High fatigue detected. You appear sleepy. Consider taking a break or resting."
    - **Restless/Anxious:** "High fatigue detected. You appear restless. Consider taking a walk or stretching."
  - Cooldown: 120 seconds

### 3. Break Needed

**Trigger:** When recommendation changes from "continue" to a break type
- **Break types:**
  - `take_short_break` - "You need a short break. Step away for a few minutes."
  - `take_long_break` - "You need a long break. Consider resting or taking a nap."
  - `take_walk` - "You need to move. Consider taking a walk or doing some stretching."
- **Cooldown:** 180 seconds

## Configuration

### Thresholds (in `notification_manager.py`)

```python
self.z_score_threshold = 0.7      # Z-score for "not locked in"
self.fatigue_score_warning = 0.5  # Fatigue score for warning
self.fatigue_score_critical = 0.7  # Fatigue score for critical alert
```

### Cooldown Periods

```python
self.cooldowns = {
    "not_locked_in": 60,      # 1 minute
    "fatigue_detected": 120,   # 2 minutes
    "break_needed": 180,       # 3 minutes
}
```

## Testing

To test notifications, start the fatigue detection server:

```powershell
# Start the server
.\start_servers.ps1

# Or manually:
$env:FATIGUE_PORT=8001
python fatigue_detection/app.py
```

The notifications will automatically appear when:
- You deviate from your baseline (fidget, look away, etc.)
- Your fatigue score increases
- The system recommends a break

## Requirements

- Windows 10/11 (for toast notifications)
- `win10toast` package (installed via `requirements.txt`)

## Troubleshooting

**Notifications not appearing:**
1. Check if `win10toast` is installed: `pip install win10toast`
2. Ensure Windows notifications are enabled in system settings
3. Check console output for notification errors
4. Verify face is being detected (notifications only trigger when face is detected)

**Too many notifications:**
- Adjust cooldown periods in `notification_manager.py`
- Increase thresholds (z_score_threshold, fatigue_score_warning, etc.)

**No notifications:**
- Make sure you've completed calibration (baseline profile exists)
- Check that `work_session_calibrated: true` in your profile JSON
- Verify the WebSocket connection is active
