# Debugging Notifications

## Why You Might Not See Notifications

### 1. Profile Not Calibrated
**Check:** Look at your profile JSON file (`fatigue_detection/profiles/your_user.json`)
- If `work_session_calibrated: false`, Z-scores won't be calculated properly
- **Solution:** Run calibration first: `.\run_calibration.ps1 --user your_user`

### 2. Face Not Detected
**Check:** Look at the camera overlay - does it say "FACE: DETECTED"?
- Notifications only trigger when `face_detected: true`
- **Solution:** Improve lighting, move closer to camera, face camera directly

### 3. Thresholds Too High
**Current thresholds (lowered for testing):**
- Z-score threshold: 0.5 (50% deviation from baseline)
- Fatigue warning: 0.3 (30% fatigue)
- Fatigue critical: 0.5 (50% fatigue)

**Check:** Look at console output for debug messages showing actual Z-scores and fatigue scores

### 4. Z-Scores Not Being Calculated
**If profile is calibrated but Z-scores are always 0:**
- The profile might not be loading correctly
- Check console for: `[FatigueEngine] Profile loaded` messages

### 5. Cooldown Periods
**Cooldowns prevent spam:**
- Not locked in: 60 seconds
- Fatigue: 120 seconds  
- Break needed: 180 seconds

If you just got a notification, wait for the cooldown to expire.

## How to Test

### Test 1: Direct Notification
```python
from notification_manager import get_notification_manager
nm = get_notification_manager()
nm._show_notification("Test", "You should see this!", duration=5)
```

### Test 2: Check Current Metrics
When the server is running, check the console output for:
```
[DEBUG] Metrics - fatigue: X.XX, Z-scores: {...}, rec: ...
```

### Test 3: Force Trigger
Temporarily lower thresholds in `notification_manager.py`:
```python
self.z_score_threshold = 0.1  # Very low - will trigger easily
self.fatigue_score_warning = 0.1
self.fatigue_score_critical = 0.2
```

## Common Issues

**"No notifications appearing"**
1. Check Windows notification settings (Settings > System > Notifications)
2. Make sure notifications aren't disabled for Python
3. Check console for error messages
4. Verify `win10toast` is installed: `pip install win10toast`

**"Notifications appear but too infrequently"**
- Lower the thresholds
- Reduce cooldown periods

**"Too many notifications"**
- Increase thresholds
- Increase cooldown periods
