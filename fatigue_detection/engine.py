"""
Python wrapper for C++ FatigueEngine.
Provides zero-copy numpy array passing to C++ module.
"""

import numpy as np
import time
import os
from typing import Optional, Dict, Any

try:
    # Add MSYS2 bin to PATH for DLLs before importing
    import os
    import sys
    
    msys2_bin = r"C:\msys64\ucrt64\bin"
    if os.path.exists(msys2_bin):
        # For Python 3.8+, use add_dll_directory (more reliable than PATH)
        if sys.version_info >= (3, 8):
            os.add_dll_directory(msys2_bin)
        # Also add to PATH as fallback
        os.environ["PATH"] = msys2_bin + os.pathsep + os.environ.get("PATH", "")
    
    # Also add current directory for DLLs (where we copied DLLs)
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if sys.version_info >= (3, 8):
        os.add_dll_directory(current_dir)
    
    import lockin_core
except ImportError as e:
    raise ImportError(
        "lockin_core module not found. Please build the C++ module first.\n"
        "Run: cd fatigue_detection/cpp && mkdir build && cd build && cmake .. && mingw32-make\n"
        "Also ensure DLLs are copied: See fatigue_detection/setup_dlls.ps1"
    ) from e


class FatigueEngine:
    """Python wrapper for C++ FatigueEngine."""
    
    def __init__(self, user_id: str, profile_path: Optional[str] = None):
        """
        Initialize FatigueEngine.
        
        Args:
            user_id: User identifier
            profile_path: Optional path to profile JSON file. If None, uses default path.
        """
        self.user_id = user_id
        
        # Default profile path
        if profile_path is None:
            profile_dir = os.path.join(os.path.dirname(__file__), "profiles")
            os.makedirs(profile_dir, exist_ok=True)
            profile_path = os.path.join(profile_dir, f"{user_id}.json")
        
        # Initialize C++ engine
        try:
            self._engine = lockin_core.FatigueEngine(user_id, profile_path)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize FatigueEngine: {e}") from e
        
        self.profile_path = profile_path
        
        # Expose C++ methods directly (for methods that don't need Python-side processing)
        # This allows direct access to methods like set_landmark_offset
        # Check if these methods exist (they may not be in all builds)
        if hasattr(self._engine, 'set_landmark_offset'):
            self.set_landmark_offset = self._engine.set_landmark_offset
        if hasattr(self._engine, 'set_eye_offset'):
            self.set_eye_offset = self._engine.set_eye_offset
        if hasattr(self._engine, 'set_mouth_offset'):
            self.set_mouth_offset = self._engine.set_mouth_offset
    
    def process_frame(self, frame: np.ndarray, timestamp_ms: Optional[int] = None) -> Dict[str, Any]:
        """
        Process a frame and return fatigue metrics.
        
        Args:
            frame: NumPy array (H, W, 3) uint8 in BGR format (OpenCV standard)
            timestamp_ms: Optional timestamp in milliseconds. If None, uses current time.
        
        Returns:
            Dictionary with fatigue metrics:
            - blink_rate: Blinks per minute
            - perclos: Percentage of eyelid closure (0-1)
            - yawn_count_5min: Yawn count in last 5 minutes
            - gaze_stability: Gaze stability score (0-1, higher = more stable)
            - fidgeting_score: Fidgeting score (0-1, higher = more fidgeting)
            - neck_crack_count_1min: Neck crack count in last minute
            - fatigue_score: Overall fatigue score (0-1)
            - fatigue_level: "focused", "moderate", or "high"
            - recommendation: "continue", "take_short_break", or "take_long_break"
            - events: List of recent events
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        
        # Validate frame
        if frame is None or frame.size == 0:
            raise ValueError("Frame is empty")
        
        if len(frame.shape) != 3 or frame.shape[2] != 3:
            raise ValueError(f"Frame must be (H, W, 3) uint8, got shape: {frame.shape}")
        
        if frame.dtype != np.uint8:
            raise ValueError(f"Frame must be uint8, got dtype: {frame.dtype}")
        
        # Ensure contiguous array for zero-copy optimization
        if not frame.flags['C_CONTIGUOUS']:
            frame = np.ascontiguousarray(frame)
        
        # Process frame with C++ engine (zero-copy if frame is contiguous)
        try:
            result = self._engine.process_frame(frame, timestamp_ms)
            
            # C++ bindings already return a dict (via state_vector_to_dict)
            # Check if result is already a dict
            if isinstance(result, dict):
                # Add face_detected flag based on whether face was found
                # (We can infer this from landmarks or face_bbox if available)
                # For now, check if any metrics indicate face was processed
                result["face_detected"] = result.get("blink_rate", 0) > 0 or result.get("gaze_stability", 0) > 0
                
                # Add backwards-compatible aliases
                result["yawn_count"] = result.get("yawn_count_5min", 0)
                result["fidget_score"] = result.get("fidgeting_score", 0.0)
                
                return result
            elif hasattr(result, 'to_dict'):
                # If it's an object with to_dict method
                result_dict = result.to_dict()
                result_dict["face_detected"] = result_dict.get("blink_rate", 0) > 0
                result_dict["yawn_count"] = result_dict.get("yawn_count_5min", 0)
                result_dict["fidget_score"] = result_dict.get("fidgeting_score", 0.0)
                return result_dict
            else:
                # Fallback: treat as object (shouldn't happen with current bindings)
                return {
                    "blink_rate": getattr(result, 'blink_rate', 0.0),
                    "perclos": getattr(result, 'perclos', 0.0),
                    "yawn_count_5min": getattr(result, 'yawn_count_5min', 0),
                    "yawn_count": getattr(result, 'yawn_count_5min', 0),
                    "gaze_stability": getattr(result, 'gaze_stability', 0.0),
                    "fidgeting_score": getattr(result, 'fidgeting_score', 0.0),
                    "fidget_score": getattr(result, 'fidgeting_score', 0.0),
                    "neck_crack_count_1min": getattr(result, 'neck_crack_count_1min', 0),
                    "fatigue_score": getattr(result, 'fatigue_score', 0.0),
                    "fatigue_level": getattr(result, 'fatigue_level', 'unknown'),
                    "recommendation": getattr(result, 'recommendation', 'continue'),
                    "events": list(getattr(result, 'events', [])) if hasattr(result, 'events') else [],
                    "face_detected": getattr(result, 'blink_rate', 0) > 0
                }
        except Exception as e:
            raise RuntimeError(f"Failed to process frame: {e}") from e
    
    def update_metrics(self, ear: float, mar: float, gaze_x: float, gaze_y: float,
                       timestamp_ms: Optional[int] = None, face_detected: bool = False,
                       head_pitch: float = 0.0, head_yaw: float = 0.0, head_roll: float = 0.0) -> Dict[str, Any]:
        """
        Update fatigue metrics directly from an external vision system (e.g., MediaPipe).
        
        Args:
            ear: Eye Aspect Ratio
            mar: Mouth Aspect Ratio
            gaze_x: Normalized horizontal gaze (yaw)
            gaze_y: Normalized vertical gaze (pitch)
            timestamp_ms: Optional timestamp in milliseconds. If None, uses current time.
            face_detected: Boolean indicating if a face was detected.
            head_pitch: Head pitch angle in degrees (for neck crack detection)
            head_yaw: Head yaw angle in degrees (for neck crack detection)
            head_roll: Head roll angle in degrees (for neck crack detection)
        
        Returns:
            Dictionary with fatigue metrics.
        """
        if timestamp_ms is None:
            timestamp_ms = int(time.time() * 1000)
        
        return self._engine.update_metrics(ear, mar, gaze_x, gaze_y, timestamp_ms, face_detected,
                                          head_pitch, head_yaw, head_roll)
    
    def load_profile(self, profile_path: Optional[str] = None) -> bool:
        """Load user profile from JSON file."""
        path = profile_path or self.profile_path
        if not path:
            return False
        
        try:
            return self._engine.load_profile(path)
        except Exception as e:
            print(f"Warning: Failed to load profile {path}: {e}")
            return False
    
    def update_profile(self, session_stats: Dict[str, float], user_rating: float):
        """
        Update profile baseline with session statistics and user rating.
        
        Args:
            session_stats: Dictionary with session statistics (e.g., average blink_rate)
            user_rating: User rating (1-10) for the session
        """
        if user_rating < 1.0 or user_rating > 10.0:
            raise ValueError(f"user_rating must be between 1.0 and 10.0, got: {user_rating}")
        
        try:
            self._engine.update_profile(session_stats, user_rating)
        except Exception as e:
            raise RuntimeError(f"Failed to update profile: {e}") from e
    
    def start_calibration_session(self, session_type: str):
        """
        Start a calibration session (work or break).
        
        Args:
            session_type: "work" or "break"
        """
        if session_type not in ["work", "break"]:
            raise ValueError(f"session_type must be 'work' or 'break', got: {session_type}")
        
        try:
            self._engine.start_calibration_session(session_type)
        except Exception as e:
            raise RuntimeError(f"Failed to start calibration session: {e}") from e
    
    def end_calibration_session(self, session_stats: Dict[str, float], user_rating: float):
        """
        End calibration session and save baseline (only if rating >= 8).
        
        Args:
            session_stats: Dictionary with session statistics
            user_rating: User rating (1-10) - only ratings >= 8 are accepted
        """
        if user_rating < 1.0 or user_rating > 10.0:
            raise ValueError(f"user_rating must be between 1.0 and 10.0, got: {user_rating}")
        
        try:
            self._engine.end_calibration_session(session_stats, user_rating)
        except Exception as e:
            raise RuntimeError(f"Failed to end calibration session: {e}") from e
    
    def is_calibrated(self) -> bool:
        """Check if user profile is calibrated."""
        try:
            return self._engine.is_calibrated()
        except Exception as e:
            raise RuntimeError(f"Failed to check calibration status: {e}") from e
    
    def set_ear_threshold(self, threshold: float):
        """Set Eye Aspect Ratio threshold for blink detection (calibration)."""
        try:
            self._engine.set_ear_threshold(threshold)
        except Exception as e:
            raise RuntimeError(f"Failed to set EAR threshold: {e}") from e
    
    def set_mar_threshold(self, threshold: float):
        """Set Mouth Aspect Ratio threshold for yawn detection (calibration)."""
        try:
            self._engine.set_mar_threshold(threshold)
        except Exception as e:
            raise RuntimeError(f"Failed to set MAR threshold: {e}") from e
    
    def get_ear_threshold(self) -> float:
        """Get current EAR threshold."""
        try:
            return self._engine.get_ear_threshold()
        except Exception as e:
            raise RuntimeError(f"Failed to get EAR threshold: {e}") from e
    
    def get_mar_threshold(self) -> float:
        """Get current MAR threshold."""
        try:
            return self._engine.get_mar_threshold()
        except Exception as e:
            raise RuntimeError(f"Failed to get MAR threshold: {e}") from e
    
    def adjust_neck_crack_thresholds(self, velocity_multiplier: float = 1.15, acceleration_multiplier: float = 1.15) -> Dict[str, float]:
        """
        Adjust neck crack detection thresholds (for false positive feedback).
        
        Args:
            velocity_multiplier: Multiply current velocity threshold by this value (default 1.15 = +15%)
            acceleration_multiplier: Multiply current acceleration threshold by this value (default 1.15 = +15%)
        
        Returns:
            Dictionary with new thresholds: {"velocity": float, "acceleration": float}
        """
        try:
            self._engine.adjust_neck_crack_thresholds(velocity_multiplier, acceleration_multiplier)
            return self.get_neck_crack_thresholds()
        except Exception as e:
            raise RuntimeError(f"Failed to adjust neck crack thresholds: {e}") from e
    
    def get_neck_crack_thresholds(self) -> Dict[str, float]:
        """Get current neck crack detection thresholds."""
        try:
            return self._engine.get_neck_crack_thresholds()
        except Exception as e:
            raise RuntimeError(f"Failed to get neck crack thresholds: {e}") from e