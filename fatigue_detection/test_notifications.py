"""
Quick test script to verify notifications are working.
"""

from notification_manager import get_notification_manager
import time

print("Testing notification system...")
print("=" * 60)

nm = get_notification_manager()

if not nm.toaster:
    print("ERROR: Toast notifier not available!")
    exit(1)

print(f"Notification manager initialized: {nm}")
print(f"Toaster available: {nm.toaster is not None}")
print(f"Debug mode: {getattr(nm, 'debug', False)}")
print(f"Thresholds:")
print(f"  Z-score: {nm.z_score_threshold}")
print(f"  Fatigue warning: {nm.fatigue_score_warning}")
print(f"  Fatigue critical: {nm.fatigue_score_critical}")
print()

# Test 1: Direct notification
print("Test 1: Direct notification...")
nm._show_notification("Test Notification", "If you see this, notifications are working!", duration=5)
time.sleep(1)
print("✓ Test notification sent")
print()

# Test 2: Not locked in (high Z-scores)
print("Test 2: Not locked in detection...")
test_metrics = {
    "face_detected": True,
    "z_score_blink": 0.3,
    "z_score_gaze": 0.4,
    "z_score_fidget": 0.8,  # High fidgeting - should trigger
    "z_score_posture": 0.2,
    "fatigue_score": 0.3,
    "recommendation": "continue"
}
result = nm.check_not_locked_in(test_metrics)
print(f"Result: {result}")
print()

# Test 3: Fatigue detection
print("Test 3: Fatigue detection...")
test_metrics = {
    "face_detected": True,
    "z_score_blink": 0.2,
    "z_score_gaze": 0.3,
    "z_score_fidget": 0.2,
    "z_score_posture": 0.2,
    "fatigue_score": 0.6,  # High fatigue - should trigger
    "fatigue_level": "high",
    "energy_type": "sleepy",
    "recommendation": "take_long_break"
}
result = nm.check_fatigue(test_metrics)
print(f"Result: {result}")
print()

# Test 4: Break needed
print("Test 4: Break needed detection...")
test_metrics = {
    "face_detected": True,
    "z_score_blink": 0.2,
    "z_score_gaze": 0.3,
    "z_score_fidget": 0.2,
    "z_score_posture": 0.2,
    "fatigue_score": 0.4,
    "recommendation": "take_short_break"
}
result = nm.check_break_needed(test_metrics, last_recommendation="continue")
print(f"Result: {result}")
print()

print("=" * 60)
print("Test complete! Check if you saw 4 notifications above.")
print("If not, check Windows notification settings.")
