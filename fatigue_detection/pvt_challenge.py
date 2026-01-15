"""
Psychomotor Vigilance Task (PVT) Challenge implementation.
Active detector that measures reaction time when fatigue is detected.
"""

import random
import time
from typing import Optional, Callable, Dict, Any


class PVTChallenge:
    """PVT Challenge manager."""
    
    def __init__(self):
        self.is_active = False
        self.start_time: Optional[float] = None
        self.delay_ms: int = 0
        self.reaction_time_ms: Optional[int] = None
        self.callback: Optional[Callable] = None
    
    def trigger(self, delay_ms: Optional[int] = None, callback: Optional[Callable] = None):
        """
        Trigger a PVT challenge.
        
        Args:
            delay_ms: Delay before challenge appears (1-5 seconds). If None, random.
            callback: Optional callback function to call when challenge appears.
        """
        if self.is_active:
            return  # Challenge already active
        
        if delay_ms is None:
            delay_ms = random.randint(1000, 5000)
        
        self.delay_ms = delay_ms
        self.callback = callback
        self.is_active = True
        self.start_time = time.time() * 1000  # milliseconds
        self.reaction_time_ms = None
    
    def on_challenge_appear(self):
        """Called when the challenge shape appears (frontend handles this)."""
        if not self.is_active:
            return
        
        self.appear_time = time.time() * 1000  # milliseconds
        
        if self.callback:
            self.callback()
    
    def record_response(self, reaction_time_ms: Optional[int] = None) -> Optional[int]:
        """
        Record user response (reaction time from frontend).
        
        Args:
            reaction_time_ms: Reaction time in milliseconds (from frontend).
                            If None, calculates from start_time (not recommended).
        
        Returns:
            Reaction time in milliseconds, or None if challenge not active.
        """
        if not self.is_active:
            return None
        
        if reaction_time_ms is not None:
            self.reaction_time_ms = reaction_time_ms
        elif self.start_time is not None:
            # Fallback: calculate from start (but frontend should send the time)
            response_time = time.time() * 1000
            self.reaction_time_ms = int(response_time - self.start_time)
        else:
            return None
        
        return self.reaction_time_ms
    
    def interpret_response(self) -> Dict[str, Any]:
        """
        Interpret the reaction time.
        
        Returns:
            Dictionary with interpretation.
        """
        if self.reaction_time_ms is None:
            return {
                "status": "no_response",
                "interpretation": "missed"
            }
        
        rt = self.reaction_time_ms
        
        if rt < 250:
            return {
                "status": "too_fast",
                "interpretation": "alert",
                "message": "False alarm - resetting fatigue score"
            }
        elif rt <= 500:
            return {
                "status": "normal",
                "interpretation": "normal",
                "message": "Normal reaction time"
            }
        elif rt <= 1000:
            return {
                "status": "slow",
                "interpretation": "impaired",
                "message": "Slowed reaction - fatigue confirmed"
            }
        else:
            return {
                "status": "very_slow",
                "interpretation": "severely_impaired",
                "message": "Severely impaired - force break recommended"
            }
    
    def reset(self):
        """Reset the challenge."""
        self.is_active = False
        self.start_time = None
        self.reaction_time_ms = None
        self.delay_ms = 0
        self.callback = None


# Global challenge instance (can be used by server)
global_pvt_challenge = PVTChallenge()


def should_trigger_pvt(fatigue_score: float, threshold: float = 0.7) -> bool:
    """Check if PVT challenge should be triggered."""
    return fatigue_score >= threshold


def interpret_reaction_time(reaction_time_ms: int) -> str:
    """Interpret reaction time and return recommendation."""
    if reaction_time_ms < 250:
        return "alert"  # False alarm
    elif reaction_time_ms <= 500:
        return "normal"
    elif reaction_time_ms <= 1000:
        return "impaired"
    else:
        return "severely_impaired"  # Microsleep
