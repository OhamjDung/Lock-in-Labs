# Troubleshooting: Why No Notifications?

## Quick Checks

### 1. **Test Notification on Connection**
When you connect to the WebSocket, you should see a test notification:
- **Title:** "Lock In Labs"
- **Message:** "Fatigue detection connected. Notifications are active!"

**If you DON'T see this:**
- Windows notifications might be disabled
- Check Windows Settings > System > Notifications
- Make sure Python apps can show notifications

### 2. **Check Console Output**
When the server is running, look for:
- `[DEBUG] Metrics - fatigue: X.XX, Z-scores: {...}`
- `[NOTIFICATION] Triggering...` messages
- `[NOTIFICATION] Not locked in alert sent...`

### 3. **Profile Status**
Check if your profile is calibrated:
- File: `fatigue_detection/profiles/your_user.json`
- Look for: `"work_session_calibrated": true`
- **If false:** Run calibration: `.\run_calibration.ps1 --user your_user`

### 4. **Face Detection**
Notifications only work when face is detected:
- Look at camera overlay - should say "FACE: DETECTED"
- If not detected: Improve lighting, face camera directly

## Current Thresholds (Lowered for Testing)

- **Z-score threshold:** 0.3 (30% deviation from baseline)
- **Fatigue warning:** 0.2 (20% fatigue)
- **Fatigue critical:** 0.3 (30% fatigue)

These are **very low** - notifications should trigger easily.

## Common Issues

### Issue: "I see the test notification but nothing else"
**Possible causes:**
1. **Z-scores are 0** - Profile not loaded or not calibrated
   - Check console for profile load messages
   - Run calibration if needed

2. **Face not detected consistently**
   - Check camera overlay
   - Improve lighting/position

3. **You're actually locked in!**
   - If you're focused, Z-scores stay low
   - Try fidgeting, looking away, or moving erratically to trigger

### Issue: "No notifications at all"
**Check:**
1. Windows notification settings
2. Console for errors
3. `win10toast` installed: `pip install win10toast`
4. Test with: `python fatigue_detection/test_notifications.py`

### Issue: "Notifications appear but too infrequent"
- Lower thresholds further in `notification_manager.py`
- Reduce cooldown periods

## How to Force a Notification

### Method 1: Temporarily Lower Thresholds
Edit `fatigue_detection/notification_manager.py`:
```python
self.z_score_threshold = 0.1  # Very low
self.fatigue_score_warning = 0.1
self.fatigue_score_critical = 0.15
```

### Method 2: Test Script
Run: `python fatigue_detection/test_notifications.py`

### Method 3: Simulate Distraction
- Fidget with your mouse
- Look away from screen
- Move your head erratically
- These should increase Z-scores

## Debug Output

The system now logs:
- Z-scores periodically (1% of frames)
- When notifications trigger
- When thresholds are close but not met

Look for these in console:
```
[DEBUG] Z-scores - blink: 0.XX, gaze: 0.XX, fidget: 0.XX, posture: 0.XX
[NOTIFICATION] Triggering 'Not Locked In' alert: ...
[NOTIFICATION] Not locked in alert sent: ...
```

## Still Not Working?

1. **Check Windows notification center** - notifications might be there but not showing as popups
2. **Restart the server** - sometimes notifications need a fresh start
3. **Check for errors** in console output
4. **Verify profile path** - make sure profile JSON exists and is readable
