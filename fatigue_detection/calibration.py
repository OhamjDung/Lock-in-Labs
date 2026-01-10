"""
Calibration system for fatigue detection.
Collects baseline statistics during work and break sessions.
"""

import time
import json
import os
import numpy as np
from typing import Dict, List, Optional
from fatigue_detection.engine import FatigueEngine


class CalibrationSession:
    """Manages a calibration session."""
    
    def __init__(self, user_id: str, mode: str = "work"):
        """
        Initialize calibration session.
        
        Args:
            user_id: User identifier
            mode: "work" or "break"
        """
        if mode not in ["work", "break"]:
            raise ValueError("mode must be 'work' or 'break'")
        
        self.user_id = user_id
        self.mode = mode
        self.start_time = None
        self.metrics_history: List[Dict] = []
        self.engine: Optional[FatigueEngine] = None
    
    def start(self, engine: FatigueEngine):
        """Start the calibration session."""
        self.engine = engine
        self.start_time = time.time()
        self.metrics_history = []
        print(f"[Calibration] Started {self.mode} session for user: {self.user_id}")
    
    def add_metrics(self, metrics: Dict):
        """Add metrics from a frame."""
        if self.start_time is None:
            raise RuntimeError("Session not started. Call start() first.")
        
        elapsed = time.time() - self.start_time
        self.metrics_history.append({
            "timestamp": time.time(),
            "elapsed_seconds": elapsed,
            **metrics
        })
    
    def end(self) -> Dict:
        """End the session and return aggregated statistics."""
        if self.start_time is None:
            raise RuntimeError("Session not started.")
        
        duration = time.time() - self.start_time
        
        if not self.metrics_history:
            raise ValueError("No metrics collected during session")
        
        # Calculate session averages
        stats = {
            "mode": self.mode,
            "duration_seconds": duration,
            "frame_count": len(self.metrics_history),
            "avg_blink_rate": np.mean([m.get("blink_rate", 0) for m in self.metrics_history]),
            "avg_gaze_stability": np.mean([m.get("gaze_stability", 1.0) for m in self.metrics_history]),
            "avg_fidgeting_score": np.mean([m.get("fidgeting_score", 0) for m in self.metrics_history]),
            "avg_perclos": np.mean([m.get("perclos", 0) for m in self.metrics_history]),
            # Standard deviations
            "std_blink_rate": np.std([m.get("blink_rate", 0) for m in self.metrics_history]),
            "std_gaze_stability": np.std([m.get("gaze_stability", 1.0) for m in self.metrics_history]),
            "std_fidgeting_score": np.std([m.get("fidgeting_score", 0) for m in self.metrics_history]),
        }
        
        print(f"[Calibration] Ended {self.mode} session. Duration: {duration:.1f}s, Frames: {len(self.metrics_history)}")
        return stats


def start_calibration_session(user_id: str, mode: str = "work", duration_minutes: int = 20) -> CalibrationSession:
    """
    Start a calibration session.
    
    Args:
        user_id: User identifier
        mode: "work" or "break"
        duration_minutes: Duration of the session in minutes
    
    Returns:
        CalibrationSession object
    """
    session = CalibrationSession(user_id, mode)
    
    # Initialize engine
    engine = FatigueEngine(user_id)
    session.start(engine)
    
    print(f"[Calibration] {mode.capitalize()} session started. Duration: {duration_minutes} minutes.")
    print(f"[Calibration] Working... (ignore this message)")
    
    # In real implementation, this would be called from the daemon server
    # For now, this is a placeholder that shows the structure
    return session


def end_calibration_session(session: CalibrationSession, user_rating: Optional[float] = None) -> Dict:
    """
    End a calibration session and optionally update profile.
    
    Args:
        session: CalibrationSession object
        user_rating: User rating (1-10) for the session quality
    
    Returns:
        Session statistics dictionary
    """
    stats = session.end()
    
    if user_rating is not None:
        if not (1.0 <= user_rating <= 10.0):
            raise ValueError("user_rating must be between 1.0 and 10.0")
        
        # Update profile if rating is high enough
        if user_rating >= 8.0:
            print(f"[Calibration] High rating ({user_rating}/10). Updating baseline...")
            if session.engine:
                session_stats = {
                    "blink_rate": stats["avg_blink_rate"],
                    "gaze_stability": stats["avg_gaze_stability"],
                    "fidgeting_score": stats["avg_fidgeting_score"],
                }
                session.engine.update_profile(session_stats, user_rating)
        elif user_rating < 5.0:
            print(f"[Calibration] Low rating ({user_rating}/10). Discarding session data.")
        else:
            print(f"[Calibration] Moderate rating ({user_rating}/10). Profile may be updated.")
    
    return stats


def run_work_calibration(user_id: str, duration_minutes: int = 20) -> Dict:
    """
    Run a work session calibration.
    
    The user should work normally for the specified duration.
    At the end, they rate their focus level (1-10).
    """
    print(f"\n{'='*60}")
    print(f"WORK CALIBRATION SESSION")
    print(f"{'='*60}")
    print(f"User: {user_id}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"\nPlease work normally for {duration_minutes} minutes.")
    print(f"The system will collect baseline data during this time.\n")
    
    session = start_calibration_session(user_id, "work", duration_minutes)
    
    # Note: In real implementation, this would be integrated with the daemon server
    # that processes frames in the background. This is a placeholder structure.
    
    # Simulate waiting for user
    print(f"\n[Press Enter when you're ready to end the session...]")
    input()
    
    # Get user rating
    while True:
        try:
            rating_str = input("\nRate your focus level during this session (1-10): ")
            rating = float(rating_str)
            if 1.0 <= rating <= 10.0:
                break
            print("Rating must be between 1 and 10.")
        except ValueError:
            print("Please enter a valid number.")
    
    stats = end_calibration_session(session, rating)
    
    print(f"\n{'='*60}")
    print(f"CALIBRATION COMPLETE")
    print(f"{'='*60}")
    print(f"Average blink rate: {stats['avg_blink_rate']:.1f} /min")
    print(f"Average gaze stability: {stats['avg_gaze_stability']:.2f}")
    print(f"Average fidgeting: {stats['avg_fidgeting_score']:.2f}")
    
    return stats


def run_break_calibration(user_id: str, duration_minutes: int = 5) -> Dict:
    """
    Run a break session calibration.
    
    The user should relax, check phone, stretch, etc.
    This captures their "natural chaos" state.
    """
    print(f"\n{'='*60}")
    print(f"BREAK CALIBRATION SESSION")
    print(f"{'='*60}")
    print(f"User: {user_id}")
    print(f"Duration: {duration_minutes} minutes")
    print(f"\nPlease take a break for {duration_minutes} minutes.")
    print(f"Check your phone, stretch, browse, etc.\n")
    
    session = start_calibration_session(user_id, "break", duration_minutes)
    
    print(f"\n[Press Enter when break is over...]")
    input()
    
    stats = end_calibration_session(session)
    
    print(f"\n{'='*60}")
    print(f"BREAK SESSION COMPLETE")
    print(f"{'='*60}")
    
    return stats


if __name__ == "__main__":
    import sys
    
    user_id = sys.argv[1] if len(sys.argv) > 1 else "default_user"
    
    print("\n" + "="*60)
    print("FATIGUE DETECTION CALIBRATION")
    print("="*60)
    print("\nThis will run a work session calibration.")
    print("Make sure the fatigue detection daemon is running in another terminal.\n")
    
    input("Press Enter to start...")
    
    try:
        stats = run_work_calibration(user_id, duration_minutes=20)
        print("\nCalibration completed successfully!")
    except KeyboardInterrupt:
        print("\n\nCalibration cancelled.")
    except Exception as e:
        print(f"\n\nError during calibration: {e}")
