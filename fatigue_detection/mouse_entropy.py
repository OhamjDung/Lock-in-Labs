"""
Mouse Dynamics Tracker - Measures mouse entropy for fatigue detection.
Tracks mouse movements and calculates entropy to detect fidgeting, burnout, or focused states.
"""

import time
import math
import threading
from collections import deque
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass

try:
    from pynput import mouse
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    print("[WARNING] pynput not available. Mouse tracking disabled. Install with: pip install pynput")


@dataclass
class MouseSample:
    """Single mouse movement sample."""
    x: float
    y: float
    timestamp: float
    dx: float = 0.0
    dy: float = 0.0
    velocity: float = 0.0
    angle: float = 0.0


class MouseEntropyTracker:
    """
    Tracks mouse movements and calculates entropy metrics.
    
    Metrics:
    - Linear entropy: Low for straight-line movements (A to B), high for circular/random
    - Velocity entropy: Variance in movement speed (high = erratic)
    - Direction entropy: Variance in movement direction (high = fidgeting)
    - Overall entropy: Combined metric (0-1, higher = more fidgeting/burnout)
    """
    
    def __init__(self, window_size: int = 100, sample_rate_ms: int = 50):
        """
        Initialize mouse tracker.
        
        Args:
            window_size: Number of samples to keep in sliding window
            sample_rate_ms: Minimum time between samples (ms)
        """
        # Always initialize these attributes first (even if pynput is not available)
        self.lock = threading.Lock()
        self.listener: Optional[mouse.Listener] = None
        self.is_running = False
        self.samples: deque = deque(maxlen=window_size)
        self.last_sample_time: float = 0.0
        self.last_position: Optional[Tuple[float, float]] = None
        
        # Entropy metrics (always initialized)
        self.linear_entropy: float = 0.0
        self.velocity_entropy: float = 0.0
        self.direction_entropy: float = 0.0
        self.overall_entropy: float = 0.0
        
        # State classification
        self.state: str = "idle"  # "focused", "fidgeting", "burnout", "idle"
        
        if not PYNPUT_AVAILABLE:
            self.enabled = False
            return
        
        self.enabled = True
        self.window_size = window_size
        self.sample_rate_ms = sample_rate_ms / 1000.0  # Convert to seconds
    
    def start(self):
        """Start mouse tracking in background thread."""
        if not self.enabled:
            print("[WARNING] Mouse tracking not enabled (pynput not available)")
            return
        
        if self.is_running:
            return
        
        try:
            self.listener = mouse.Listener(on_move=self._on_move)
            self.listener.start()
            self.is_running = True
            print("[INFO] Mouse entropy tracker started")
        except Exception as e:
            print(f"[ERROR] Failed to start mouse tracker: {e}")
            self.enabled = False
    
    def stop(self):
        """Stop mouse tracking."""
        if hasattr(self, 'listener') and self.listener:
            self.listener.stop()
            self.listener = None
        self.is_running = False
        print("[INFO] Mouse entropy tracker stopped")
    
    def _on_move(self, x: float, y: float):
        """Callback for mouse movement events."""
        current_time = time.time()
        
        # Throttle samples
        if current_time - self.last_sample_time < self.sample_rate_ms:
            return
        
        with self.lock:
            # Calculate delta from last position
            dx = 0.0
            dy = 0.0
            velocity = 0.0
            angle = 0.0
            
            if self.last_position is not None:
                dx = x - self.last_position[0]
                dy = y - self.last_position[1]
                dt = current_time - self.last_sample_time
                
                if dt > 0:
                    velocity = math.sqrt(dx*dx + dy*dy) / dt  # pixels per second
                    if dx != 0 or dy != 0:
                        angle = math.atan2(dy, dx)  # radians
            
            # Create sample
            sample = MouseSample(
                x=x,
                y=y,
                timestamp=current_time,
                dx=dx,
                dy=dy,
                velocity=velocity,
                angle=angle
            )
            
            self.samples.append(sample)
            self.last_position = (x, y)
            self.last_sample_time = current_time
            
            # Update entropy metrics periodically (every 10 samples to save CPU)
            if len(self.samples) % 10 == 0:
                self._update_entropy()
    
    def _update_entropy(self):
        """Calculate entropy metrics from recent samples."""
        if len(self.samples) < 10:
            self.overall_entropy = 0.0
            self.state = "idle"
            return
        
        samples_list = list(self.samples)
        
        # 1. Linear Entropy: How straight are the movements?
        # Low entropy = straight lines (focused), high entropy = circular/random (fidgeting)
        linear_entropy = self._calculate_linear_entropy(samples_list)
        
        # 2. Velocity Entropy: Variance in speed
        # Low = consistent speed (focused), high = erratic speed changes (burnout)
        velocity_entropy = self._calculate_velocity_entropy(samples_list)
        
        # 3. Direction Entropy: Variance in movement direction
        # Low = consistent direction (focused), high = random directions (fidgeting)
        direction_entropy = self._calculate_direction_entropy(samples_list)
        
        # Store metrics
        self.linear_entropy = linear_entropy
        self.velocity_entropy = velocity_entropy
        self.direction_entropy = direction_entropy
        
        # Combined entropy (weighted average)
        self.overall_entropy = (
            0.4 * linear_entropy +
            0.3 * velocity_entropy +
            0.3 * direction_entropy
        )
        
        # Classify state
        if self.overall_entropy < 0.3:
            self.state = "focused"  # Smooth, linear movements
        elif self.overall_entropy < 0.6:
            self.state = "fidgeting"  # Some random movement
        elif self.overall_entropy < 0.85:
            self.state = "burnout"  # Erratic movements, aggressive
        else:
            self.state = "idle"  # Very high entropy (almost no movement or completely random)
    
    def _calculate_linear_entropy(self, samples: List[MouseSample]) -> float:
        """
        Calculate linear entropy: how straight are movement paths?
        Uses path efficiency (straight-line distance / actual path distance).
        """
        if len(samples) < 2:
            return 0.0
        
        # Calculate actual path distance
        path_distance = 0.0
        for i in range(1, len(samples)):
            dx = samples[i].x - samples[i-1].x
            dy = samples[i].y - samples[i-1].y
            path_distance += math.sqrt(dx*dx + dy*dy)
        
        # Calculate straight-line distance from start to end
        start = samples[0]
        end = samples[-1]
        straight_distance = math.sqrt(
            (end.x - start.x)**2 + (end.y - start.y)**2
        )
        
        if path_distance == 0:
            return 1.0  # No movement = high entropy (idle/random)
        
        # Efficiency: 1.0 = perfectly straight, 0.0 = completely circular/random
        efficiency = straight_distance / path_distance
        
        # Convert to entropy: 1.0 - efficiency (high efficiency = low entropy)
        entropy = 1.0 - efficiency
        return max(0.0, min(1.0, entropy))
    
    def _calculate_velocity_entropy(self, samples: List[MouseSample]) -> float:
        """
        Calculate velocity entropy: variance in movement speed.
        High variance = erratic movements (burnout).
        """
        if len(samples) < 2:
            return 0.0
        
        velocities = [s.velocity for s in samples if s.velocity > 0]
        if len(velocities) < 2:
            return 0.0
        
        # Calculate coefficient of variation (CV = std/mean)
        mean_velocity = sum(velocities) / len(velocities)
        if mean_velocity == 0:
            return 0.0
        
        variance = sum((v - mean_velocity)**2 for v in velocities) / len(velocities)
        std_dev = math.sqrt(variance)
        cv = std_dev / mean_velocity
        
        # Normalize CV to 0-1 range (cap at 2.0 for CV, then normalize)
        entropy = min(1.0, cv / 2.0)
        return entropy
    
    def _calculate_direction_entropy(self, samples: List[MouseSample]) -> float:
        """
        Calculate direction entropy: variance in movement direction.
        Uses circular variance of angles.
        """
        if len(samples) < 2:
            return 0.0
        
        # Get angles for movements with significant distance
        angles = []
        for sample in samples:
            if sample.velocity > 10:  # Only consider movements > 10 pixels/sec
                angles.append(sample.angle)
        
        if len(angles) < 2:
            return 0.0
        
        # Calculate circular variance (1 - |mean vector|)
        # Convert angles to unit vectors
        mean_cos = sum(math.cos(a) for a in angles) / len(angles)
        mean_sin = sum(math.sin(a) for a in angles) / len(angles)
        mean_vector_length = math.sqrt(mean_cos**2 + mean_sin**2)
        
        # Circular variance: 0 = all directions same, 1 = completely random
        circular_variance = 1.0 - mean_vector_length
        
        return circular_variance
    
    def get_metrics(self) -> Dict:
        """
        Get current mouse entropy metrics.
        
        Returns:
            Dictionary with:
            - mouse_entropy: Overall entropy (0-1)
            - linear_entropy: Linear entropy (0-1)
            - velocity_entropy: Velocity entropy (0-1)
            - direction_entropy: Direction entropy (0-1)
            - mouse_state: "focused", "fidgeting", "burnout", or "idle"
            - sample_count: Number of samples in window
        """
        with self.lock:
            return {
                "mouse_entropy": getattr(self, 'overall_entropy', 0.0),
                "linear_entropy": getattr(self, 'linear_entropy', 0.0),
                "velocity_entropy": getattr(self, 'velocity_entropy', 0.0),
                "direction_entropy": getattr(self, 'direction_entropy', 0.0),
                "mouse_state": getattr(self, 'state', 'idle'),
                "sample_count": len(self.samples),
                "enabled": getattr(self, 'enabled', False) and getattr(self, 'is_running', False)
            }


# Global tracker instance
_global_tracker: Optional[MouseEntropyTracker] = None


def get_global_tracker() -> MouseEntropyTracker:
    """Get or create global mouse tracker instance."""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = MouseEntropyTracker()
    return _global_tracker
