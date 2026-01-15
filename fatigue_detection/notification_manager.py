"""
Desktop notification manager for fatigue detection alerts.
Shows Windows toast notifications when user is not locked in, fatigued, or needs a break.
"""

import time
from typing import Dict, Optional
from threading import Lock

try:
    from win10toast import ToastNotifier
    TOAST_AVAILABLE = True
except ImportError:
    TOAST_AVAILABLE = False
    print("[WARNING] win10toast not available. Desktop notifications disabled.")


class NotificationManager:
    """Manages desktop notifications with cooldown periods to prevent spam."""
    
    def __init__(self):
        """Initialize notification manager."""
        self.toaster: Optional[ToastNotifier] = None
        if TOAST_AVAILABLE:
            try:
                self.toaster = ToastNotifier()
            except Exception as e:
                print(f"[WARNING] Failed to initialize toast notifier: {e}")
                self.toaster = None
        
        # Cooldown periods (in seconds) to prevent notification spam
        self.cooldowns = {
            "not_locked_in": 60,      # 1 minute between "not locked in" notifications
            "fatigue_detected": 120,  # 2 minutes between fatigue notifications
            "break_needed": 180,      # 3 minutes between break notifications
        }
        
        # Track last notification time for each type
        self.last_notification_time: Dict[str, float] = {}
        self.lock = Lock()
        
        # Notification thresholds
        # NOTE: Lowered thresholds for easier testing - adjust as needed
        self.z_score_threshold = 0.3  # Z-score above this = significant deviation (not locked in) - VERY LOW for testing
        self.fatigue_score_warning = 0.2  # Fatigue score threshold for warning - VERY LOW for testing
        self.fatigue_score_critical = 0.3  # Fatigue score threshold for critical alert - VERY LOW for testing
        
        # Debug mode (set to True to see what's happening)
        self.debug = True
    
    def _can_send_notification(self, notification_type: str) -> bool:
        """Check if enough time has passed since last notification of this type."""
        with self.lock:
            if notification_type not in self.last_notification_time:
                return True
            
            elapsed = time.time() - self.last_notification_time[notification_type]
            cooldown = self.cooldowns.get(notification_type, 60)
            
            return elapsed >= cooldown
    
    def _record_notification(self, notification_type: str):
        """Record that a notification was sent."""
        with self.lock:
            self.last_notification_time[notification_type] = time.time()
    
    def _show_notification(self, title: str, message: str, duration: int = 5):
        """Show a desktop notification."""
        if not self.toaster:
            return False
        
        try:
            self.toaster.show_toast(
                title=title,
                msg=message,
                duration=duration,
                threaded=True
            )
            return True
        except Exception as e:
            print(f"[ERROR] Failed to show notification: {e}")
            return False
    
    def check_not_locked_in(self, metrics: Dict) -> bool:
        """
        Check if user is not locked in (distracted) based on Z-scores.
        
        Args:
            metrics: Dictionary containing z_score_* fields
            
        Returns:
            True if notification was sent, False otherwise
        """
        if not self._can_send_notification("not_locked_in"):
            return False
        
        # Get Z-scores
        z_score_blink = metrics.get("z_score_blink", 0.0)
        z_score_gaze = metrics.get("z_score_gaze", 0.0)
        z_score_fidget = metrics.get("z_score_fidget", 0.0)
        z_score_posture = metrics.get("z_score_posture", 0.0)
        
        # Debug: Log Z-scores periodically
        import random
        if random.random() < 0.01:  # Log 1% of the time to avoid spam
            print(f"[DEBUG] Z-scores - blink: {z_score_blink:.2f}, gaze: {z_score_gaze:.2f}, fidget: {z_score_fidget:.2f}, posture: {z_score_posture:.2f}")
        
        # Calculate average Z-score (deviation from baseline)
        avg_z_score = (z_score_blink + z_score_gaze + z_score_fidget + z_score_posture) / 4.0
        
        # Check if any Z-score exceeds threshold (significant deviation)
        max_z_score = max(z_score_blink, z_score_gaze, z_score_fidget, z_score_posture)
        
        if max_z_score >= self.z_score_threshold:
            # Determine what's causing the deviation
            if z_score_fidget > z_score_blink and z_score_fidget > z_score_gaze:
                reason = "High fidgeting detected"
            elif z_score_gaze > z_score_blink and z_score_gaze > z_score_fidget:
                reason = "Gaze instability detected"
            elif z_score_blink > z_score_gaze and z_score_blink > z_score_fidget:
                reason = "Unusual blink pattern"
            else:
                reason = "Behavior deviation detected"
            
            if self.debug:
                print(f"[NOTIFICATION] Triggering 'Not Locked In' alert: {reason} (Z-score: {max_z_score:.2f}, threshold: {self.z_score_threshold})")
            
            if self._show_notification(
                title="🔓 Not Locked In",
                message=f"{reason}. You're deviating from your focus baseline.",
                duration=5
            ):
                self._record_notification("not_locked_in")
                print(f"[NOTIFICATION] Not locked in alert sent: {reason} (Z-score: {max_z_score:.2f})")
                return True
        elif self.debug and max_z_score > 0.3:
            # Debug: Log when close to threshold
            print(f"[DEBUG] Z-score below threshold: {max_z_score:.2f} < {self.z_score_threshold} (blink:{z_score_blink:.2f}, gaze:{z_score_gaze:.2f}, fidget:{z_score_fidget:.2f}, posture:{z_score_posture:.2f})")
        
        return False
    
    def check_fatigue(self, metrics: Dict) -> bool:
        """
        Check if user is fatigued and send notification.
        
        Args:
            metrics: Dictionary containing fatigue_score and fatigue_level
            
        Returns:
            True if notification was sent, False otherwise
        """
        fatigue_score = metrics.get("fatigue_score", 0.0)
        fatigue_level = metrics.get("fatigue_level", "unknown")
        energy_type = metrics.get("energy_type", "unknown")
        
        # Critical fatigue
        if fatigue_score >= self.fatigue_score_critical:
            if not self._can_send_notification("fatigue_detected"):
                if self.debug:
                    print(f"[DEBUG] Fatigue notification on cooldown (score: {fatigue_score:.2f})")
                return False
            
            if self.debug:
                print(f"[NOTIFICATION] Triggering fatigue alert: {fatigue_level} (score: {fatigue_score:.2f}, threshold: {self.fatigue_score_critical})")
            
            if energy_type == "sleepy":
                message = "High fatigue detected. You appear sleepy. Consider taking a break or resting."
            elif energy_type == "anxious" or energy_type == "restless":
                message = "High fatigue detected. You appear restless. Consider taking a walk or stretching."
            else:
                message = "High fatigue detected. Consider taking a break."
            
            if self._show_notification(
                title="⚠️ High Fatigue Detected",
                message=message,
                duration=8
            ):
                self._record_notification("fatigue_detected")
                print(f"[NOTIFICATION] Fatigue alert sent: {fatigue_level} (score: {fatigue_score:.2f})")
                return True
        
        # Warning fatigue - less frequent
        elif fatigue_score >= self.fatigue_score_warning:
            # Use longer cooldown for warnings
            if not self._can_send_notification("fatigue_detected"):
                return False
            
            # Only notify if it's been a while (warnings are less urgent)
            if self._show_notification(
                title="💤 Fatigue Warning",
                message=f"Moderate fatigue detected ({fatigue_level}). You may want to take a short break soon.",
                duration=5
            ):
                self._record_notification("fatigue_detected")
                print(f"[NOTIFICATION] Fatigue warning: {fatigue_level} (score: {fatigue_score:.2f})")
                return True
        
        return False
    
    def check_break_needed(self, metrics: Dict, last_recommendation: Optional[str] = None) -> bool:
        """
        Check if user needs a break based on recommendation change.
        
        Args:
            metrics: Dictionary containing recommendation
            last_recommendation: Previous recommendation to detect changes
            
        Returns:
            True if notification was sent, False otherwise
        """
        recommendation = metrics.get("recommendation", "continue")
        
        # Only notify if recommendation changed to a break type
        if recommendation in ["take_short_break", "take_long_break", "take_walk"]:
            # Check if this is a new recommendation (changed from "continue")
            if last_recommendation == "continue" or last_recommendation is None:
                if not self._can_send_notification("break_needed"):
                    return False
                
                if recommendation == "take_long_break":
                    message = "You need a long break. Consider resting or taking a nap."
                elif recommendation == "take_walk":
                    message = "You need to move. Consider taking a walk or doing some stretching."
                else:
                    message = "You need a short break. Step away for a few minutes."
                
                if self._show_notification(
                    title="⏸️ Break Recommended",
                    message=message,
                    duration=6
                ):
                    self._record_notification("break_needed")
                    print(f"[NOTIFICATION] Break recommended: {recommendation}")
                    return True
        
        return False


# Global notification manager instance
_notification_manager: Optional[NotificationManager] = None


def get_notification_manager() -> NotificationManager:
    """Get or create the global notification manager instance."""
    global _notification_manager
    if _notification_manager is None:
        _notification_manager = NotificationManager()
    return _notification_manager
