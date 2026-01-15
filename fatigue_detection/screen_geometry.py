"""
Gate 2: Focus Gate - Screen Boundary Detection
Determines if user is looking at screen or away based on gaze coordinates.
"""

import sys
from typing import Tuple, List, Optional

# Attempt to import screeninfo for multi-monitor support
try:
    from screeninfo import get_monitors, Monitor
    SCREENINFO_AVAILABLE = True
except ImportError:
    SCREENINFO_AVAILABLE = False
    print("[ScreenGeometry] Warning: screeninfo not installed. Using default single monitor.")
    print("Install with: pip install screeninfo")


class ScreenGeometry:
    """
    Tracks screen boundaries and maps gaze coordinates to screen space.
    
    Gaze coordinates from FatigueEngine are normalized:
    - gaze_x, gaze_y: [-0.5, 0.5] where (0, 0) is center of face
    
    This module checks if gaze falls within screen boundaries with tolerance.
    """
    
    def __init__(self, tolerance: float = 0.15):
        """
        Initialize screen geometry detector.
        
        Args:
            tolerance: How far outside screen bounds is still considered "looking at screen"
                      (e.g., 0.15 = allow 15% beyond edges for natural eye movement)
        """
        self.tolerance = tolerance
        self.monitors: List[Monitor] = []
        self.primary_monitor: Optional[Monitor] = None
        
        if SCREENINFO_AVAILABLE:
            try:
                self.monitors = get_monitors()
                # Find primary monitor
                for monitor in self.monitors:
                    if monitor.is_primary:
                        self.primary_monitor = monitor
                        break
                
                # Fallback to first monitor if no primary found
                if self.primary_monitor is None and self.monitors:
                    self.primary_monitor = self.monitors[0]
                
                if self.primary_monitor:
                    print(f"[ScreenGeometry] Primary monitor: {self.primary_monitor.width}x{self.primary_monitor.height}")
                else:
                    print("[ScreenGeometry] No monitors detected. Using defaults.")
            except Exception as e:
                print(f"[ScreenGeometry] Error detecting monitors: {e}")
        else:
            print("[ScreenGeometry] Using default screen configuration.")
    
    def is_looking_at_screen(self, gaze_x: float, gaze_y: float) -> bool:
        """
        Check if gaze coordinates fall within screen boundaries (with tolerance).
        
        Args:
            gaze_x: Normalized gaze X coordinate [-0.5, 0.5]
            gaze_y: Normalized gaze Y coordinate [-0.5, 0.5]
            
        Returns:
            True if looking at screen, False if looking away
            
        Notes:
            - Gaze coordinates are relative to face center
            - Tolerance allows for natural eye movement beyond strict screen bounds
            - (0, 0) = looking straight ahead (center of face)
            - (-0.5, 0) = looking far left
            - (+0.5, 0) = looking far right
            - (0, -0.5) = looking up
            - (0, +0.5) = looking down
            
        Example:
            >>> screen = ScreenGeometry(tolerance=0.15)
            >>> screen.is_looking_at_screen(0.0, 0.0)  # Center
            True
            >>> screen.is_looking_at_screen(0.6, 0.0)  # Far right (beyond threshold)
            False
        """
        # Base threshold (screen bounds in normalized coordinates)
        # Assume screen takes up roughly [-0.5, 0.5] in normalized gaze space
        threshold_x = 0.5 + self.tolerance
        threshold_y = 0.5 + self.tolerance
        
        # Check if within bounds
        looking_horizontal = abs(gaze_x) <= threshold_x
        looking_vertical = abs(gaze_y) <= threshold_y
        
        return looking_horizontal and looking_vertical
    
    def get_gaze_region(self, gaze_x: float, gaze_y: float) -> str:
        """
        Classify where user is looking.
        
        Args:
            gaze_x: Normalized gaze X coordinate [-0.5, 0.5]
            gaze_y: Normalized gaze Y coordinate [-0.5, 0.5]
            
        Returns:
            Region string: "screen", "left", "right", "up", "down", or "away"
            
        Example:
            >>> screen.get_gaze_region(0.0, 0.0)
            'screen'
            >>> screen.get_gaze_region(-0.6, 0.0)
            'left'
        """
        if self.is_looking_at_screen(gaze_x, gaze_y):
            return "screen"
        
        # Determine primary direction of off-screen gaze
        abs_x = abs(gaze_x)
        abs_y = abs(gaze_y)
        
        # Horizontal dominates
        if abs_x > abs_y:
            return "left" if gaze_x < 0 else "right"
        # Vertical dominates
        else:
            return "up" if gaze_y < 0 else "down"
    
    def calibrate_screen_bounds(self, calibration_points: List[Tuple[float, float]]):
        """
        Calibrate screen boundaries based on actual gaze measurements.
        
        Args:
            calibration_points: List of (gaze_x, gaze_y) tuples collected while
                              user looks at screen corners and edges
                              
        Notes:
            This allows personalizing screen bounds based on how the user's
            gaze system interprets "screen edges" vs their actual monitor.
            
        Example:
            >>> # User looks at 4 corners of screen during calibration
            >>> corners = [(-0.45, -0.40), (0.45, -0.40), (-0.45, 0.40), (0.45, 0.40)]
            >>> screen.calibrate_screen_bounds(corners)
        """
        if not calibration_points:
            return
        
        # Find max extents
        max_x = max(abs(x) for x, y in calibration_points)
        max_y = max(abs(y) for x, y in calibration_points)
        
        # Update tolerance to match measured bounds
        self.tolerance = max(max_x - 0.5, max_y - 0.5, 0.0)
        
        print(f"[ScreenGeometry] Calibrated screen bounds: tolerance = {self.tolerance:.3f}")
    
    def get_focus_multiplier(self, gaze_x: float, gaze_y: float, phone_detected: bool) -> float:
        """
        Calculate focus multiplier for Gate 2.
        
        Args:
            gaze_x: Normalized gaze X coordinate
            gaze_y: Normalized gaze Y coordinate
            phone_detected: Whether phone is detected in frame
            
        Returns:
            Focus multiplier (0.0 or 1.0)
            
        Logic:
            - Looking at screen AND no phone: 1.0 (full focus)
            - Looking away OR phone detected: 0.0 (no focus)
        """
        looking_at_screen = self.is_looking_at_screen(gaze_x, gaze_y)
        
        if looking_at_screen and not phone_detected:
            return 1.0
        else:
            return 0.0
    
    def get_multi_monitor_info(self) -> dict:
        """
        Get information about all detected monitors.
        
        Returns:
            Dictionary with monitor information
        """
        if not SCREENINFO_AVAILABLE or not self.monitors:
            return {"count": 0, "monitors": [], "primary": None}
        
        monitors_info = []
        for i, monitor in enumerate(self.monitors):
            monitors_info.append({
                "index": i,
                "width": monitor.width,
                "height": monitor.height,
                "x": monitor.x,
                "y": monitor.y,
                "is_primary": monitor.is_primary if hasattr(monitor, 'is_primary') else False
            })
        
        primary_idx = None
        if self.primary_monitor:
            for i, m in enumerate(self.monitors):
                if m == self.primary_monitor:
                    primary_idx = i
                    break
        
        return {
            "count": len(self.monitors),
            "monitors": monitors_info,
            "primary": primary_idx
        }


# Example usage / testing
if __name__ == "__main__":
    screen = ScreenGeometry(tolerance=0.15)
    
    print("Screen Geometry - Gate 2 Focus Detection")
    print("=" * 60)
    
    # Display monitor info
    monitor_info = screen.get_multi_monitor_info()
    print(f"\nDetected Monitors: {monitor_info['count']}")
    for m in monitor_info['monitors']:
        primary = " [PRIMARY]" if m['is_primary'] else ""
        print(f"  Monitor {m['index']}: {m['width']}x{m['height']} at ({m['x']}, {m['y']}){primary}")
    
    # Test gaze positions
    print("\nTesting Gaze Positions:")
    print("-" * 60)
    
    test_points = [
        (0.0, 0.0, "Center of screen"),
        (0.3, 0.2, "Upper right quadrant"),
        (-0.4, -0.3, "Upper left quadrant"),
        (0.6, 0.0, "Far right (off-screen)"),
        (-0.7, 0.0, "Far left (off-screen)"),
        (0.0, -0.6, "Looking up (off-screen)"),
        (0.0, 0.7, "Looking down (off-screen)"),
    ]
    
    for gaze_x, gaze_y, description in test_points:
        looking = screen.is_looking_at_screen(gaze_x, gaze_y)
        region = screen.get_gaze_region(gaze_x, gaze_y)
        multiplier = screen.get_focus_multiplier(gaze_x, gaze_y, phone_detected=False)
        
        status = "✓ ON SCREEN" if looking else "✗ OFF SCREEN"
        print(f"{status:15s} | Region: {region:8s} | Multiplier: {multiplier:.1f} | {description}")
    
    print("\n" + "=" * 60)
    print("Configuration:")
    print(f"  Tolerance: {screen.tolerance:.2f}")
    print(f"  Max gaze bounds: ±{0.5 + screen.tolerance:.2f}")
