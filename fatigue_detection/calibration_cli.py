"""
Standalone CLI script for two-phase calibration (Work → Break).
Collects baseline statistics during focused work and break sessions.
"""

import cv2
import time
import argparse
import numpy as np
import sys
import os
from typing import Dict, List, Optional

# Add project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fatigue_detection.engine import FatigueEngine


class TrainingSession:
    """Manages a two-phase training session (Work → Break)."""
    
    def __init__(self, user_id: str, work_duration_min: int = 30, break_duration_min: int = 5, camera_index: int = 0):
        """
        Initialize training session.
        
        Args:
            user_id: User identifier
            work_duration_min: Duration of work phase in minutes
            break_duration_min: Duration of break phase in minutes
            camera_index: Camera device index (default: 0). Use 1, 2, etc. if you have multiple cameras.
        """
        self.user_id = user_id
        self.work_duration = work_duration_min * 60  # Convert to seconds
        self.break_duration = break_duration_min * 60
        self.work_data: List[Dict] = []  # List of StateVector dicts from work phase
        self.break_data: List[Dict] = []  # List of StateVector dicts from break phase
        self.engine: Optional[FatigueEngine] = None
        self.camera: Optional[cv2.VideoCapture] = None
        self.user_rating: Optional[float] = None  # Store rating from work phase
        self.camera_index = camera_index
    
    def initialize(self):
        """Initialize engine and camera."""
        print(f"[Training] Initializing for user: {self.user_id}")
        
        # Initialize engine
        try:
            self.engine = FatigueEngine(self.user_id)
            print("[Training] Engine initialized")
        except Exception as e:
            raise RuntimeError(f"Failed to initialize engine: {e}") from e
        
        # Initialize camera (use camera_index if provided, otherwise default to 0)
        camera_index = getattr(self, 'camera_index', 0)
        self.camera = cv2.VideoCapture(camera_index)
        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_index}. Make sure no other process is using it.")
        
        # Set camera properties
        self.camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
        
        actual_width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        print(f"[Training] Camera opened: {actual_width}x{actual_height}")
    
    def cleanup(self):
        """Release camera and cleanup resources."""
        if self.camera:
            self.camera.release()
        cv2.destroyAllWindows()
    
    def format_time(self, seconds: float) -> str:
        """Format seconds as MM:SS."""
        mins = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{mins:02d}:{secs:02d}"
    
    def draw_phase1_overlay(self, frame: np.ndarray, elapsed: float, remaining: float, frame_count: int) -> np.ndarray:
        """Draw Phase 1 (Work) overlay."""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        
        # Top banner - Phase 1: LOCK IN (blue background)
        banner_height = 80
        cv2.rectangle(overlay, (0, 0), (w, banner_height), (100, 50, 200), -1)
        cv2.putText(overlay, "PHASE 1: LOCK IN", (20, 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        cv2.putText(overlay, "Welcome to Lock In Labs. To learn your style, please work on a task. Ignore us.",
                   (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Center - Time remaining (large text)
        time_text = f"Time Remaining: {self.format_time(remaining)}"
        (text_width, text_height), baseline = cv2.getTextSize(time_text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
        text_x = (w - text_width) // 2
        text_y = (h + text_height) // 2
        cv2.putText(overlay, time_text, (text_x, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        
        # Bottom - Frames collected
        bottom_text = f"Frames: {frame_count:,} | Rating: (waiting...)"
        cv2.putText(overlay, bottom_text, (20, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        
        return overlay
    
    def draw_phase2_overlay(self, frame: np.ndarray, elapsed: float, remaining: float, frame_count: int) -> np.ndarray:
        """Draw Phase 2 (Break) overlay."""
        h, w = frame.shape[:2]
        overlay = frame.copy()
        
        # Top banner - Phase 2: RELAX (green background)
        banner_height = 80
        cv2.rectangle(overlay, (0, 0), (w, banner_height), (50, 200, 100), -1)
        cv2.putText(overlay, "PHASE 2: RELAX", (20, 35),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        cv2.putText(overlay, "Great job. Now, take a break. Check your phone, stretch, or browse YouTube.",
                   (20, 65), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Center - Time remaining
        time_text = f"Time Remaining: {self.format_time(remaining)}"
        (text_width, text_height), baseline = cv2.getTextSize(time_text, cv2.FONT_HERSHEY_SIMPLEX, 1.5, 3)
        text_x = (w - text_width) // 2
        text_y = (h + text_height) // 2
        cv2.putText(overlay, time_text, (text_x, text_y),
                   cv2.FONT_HERSHEY_SIMPLEX, 1.5, (255, 255, 255), 3)
        
        # Bottom - Instructions
        bottom_text = f"Frames: {frame_count:,} | Check phone, stretch, browse"
        cv2.putText(overlay, bottom_text, (20, h - 20),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (200, 200, 200), 2)
        
        return overlay
    
    def run_work_phase(self) -> bool:
        """
        Collect work session data.
        
        Returns:
            True if rating >= 8 (should continue to break phase), False otherwise
        """
        if not self.engine or not self.camera:
            raise RuntimeError("Session not initialized. Call initialize() first.")
        
        print(f"\n{'='*60}")
        print(f"PHASE 1: WORK SESSION")
        print(f"{'='*60}")
        print(f"Duration: {self.work_duration // 60} minutes")
        print(f"Please work normally on a task. The system will collect baseline data.")
        print(f"Press 'q' in the camera window to abort.\n")
        
        # Start calibration session
        self.engine.start_calibration_session("work")
        
        # Create window
        window_name = "Training Mode - Phase 1: Lock In"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        
        start_time = time.time()
        frame_count = 0
        
        print("[Training] Starting work phase...")
        
        while True:
            ret, frame = self.camera.read()
            if not ret:
                time.sleep(0.033)
                continue
            
            elapsed = time.time() - start_time
            remaining = max(0, self.work_duration - elapsed)
            
            # Process frame
            try:
                timestamp_ms = int(time.time() * 1000)
                metrics = self.engine.process_frame(frame, timestamp_ms)
                
                # Only store metrics when face is detected
                if metrics.get("face_detected", False):
                    self.work_data.append(metrics)
                    frame_count += 1
            except Exception as e:
                print(f"[WARNING] Frame processing error: {e}")
                metrics = {"face_detected": False}
            
            # Draw overlay
            overlay = self.draw_phase1_overlay(frame, elapsed, remaining, frame_count)
            cv2.imshow(window_name, overlay)
            
            # Check for exit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 'q' or ESC
                print("\n[Training] Work phase aborted by user")
                cv2.destroyWindow(window_name)
                return False
            
            # Check if time is up
            if elapsed >= self.work_duration:
                break
        
        cv2.destroyWindow(window_name)
        
        print(f"\n[Training] Work phase complete!")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Frames collected: {frame_count:,}")
        print(f"  Valid frames (face detected): {len(self.work_data):,}")
        
        if len(self.work_data) < 10:
            print("\n[WARNING] Very few frames with face detected. Calibration may be inaccurate.")
            print("Make sure you're facing the camera with good lighting.")
        
        # Prompt for rating
        print(f"\n{'='*60}")
        while True:
            try:
                rating_str = input("Rate your focus level during this session (1-10): ")
                rating = float(rating_str)
                if 1.0 <= rating <= 10.0:
                    break
                print("Rating must be between 1 and 10.")
            except ValueError:
                print("Please enter a valid number.")
        
        print(f"\n[Training] You rated your focus: {rating}/10")
        
        # Store rating for later use
        self.user_rating = rating
        
        if rating < 5.0:
            print("[Training] Rating too low (< 5). Discarding session data.")
            return False
        elif rating < 8.0:
            print("[Training] Rating moderate (5-7). Session will be saved but with lower weight.")
            # Still continue to break phase, but note the rating
        else:
            print("[Training] High rating (>= 8). This will be saved as the 'Golden Standard' baseline.")
        
        return True
    
    def run_break_phase(self):
        """Collect break session data."""
        if not self.engine or not self.camera:
            raise RuntimeError("Session not initialized.")
        
        print(f"\n{'='*60}")
        print(f"PHASE 2: BREAK SESSION")
        print(f"{'='*60}")
        print(f"Duration: {self.break_duration // 60} minutes")
        print(f"Please relax: check your phone, stretch, browse YouTube, etc.")
        print(f"This captures your 'Natural Chaos' state.\n")
        
        # Create window
        window_name = "Training Mode - Phase 2: Relax"
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        
        start_time = time.time()
        frame_count = 0
        
        print("[Training] Starting break phase...")
        
        while True:
            ret, frame = self.camera.read()
            if not ret:
                time.sleep(0.033)
                continue
            
            elapsed = time.time() - start_time
            remaining = max(0, self.break_duration - elapsed)
            
            # Process frame
            try:
                timestamp_ms = int(time.time() * 1000)
                metrics = self.engine.process_frame(frame, timestamp_ms)
                
                # Store all metrics (even without face - captures chaos state)
                self.break_data.append(metrics)
                if metrics.get("face_detected", False):
                    frame_count += 1
            except Exception as e:
                print(f"[WARNING] Frame processing error: {e}")
                metrics = {"face_detected": False}
                self.break_data.append(metrics)
            
            # Draw overlay
            overlay = self.draw_phase2_overlay(frame, elapsed, remaining, len(self.break_data))
            cv2.imshow(window_name, overlay)
            
            # Check for exit
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == 27:  # 'q' or ESC
                print("\n[Training] Break phase aborted by user")
                break
            
            # Check if time is up
            if elapsed >= self.break_duration:
                break
        
        cv2.destroyWindow(window_name)
        
        print(f"\n[Training] Break phase complete!")
        print(f"  Duration: {elapsed:.1f} seconds")
        print(f"  Total frames: {len(self.break_data):,}")
        print(f"  Frames with face: {frame_count:,}")
    
    def aggregate_statistics(self, data: List[Dict]) -> Dict:
        """
        Aggregate StateVector metrics into session statistics.
        
        Args:
            data: List of StateVector dictionaries
            
        Returns:
            Dictionary with aggregated statistics (mean and std dev)
        """
        if not data:
            raise ValueError("No data to aggregate")
        
        # Fields to aggregate from StateVector
        fields = [
            'blink_rate',
            'perclos',
            'gaze_stability',
            'fidgeting_score',
            'current_ear',
            'current_mar'
        ]
        
        stats = {}
        
        # Filter to only frames with face detected for most metrics
        face_detected_data = [d for d in data if d.get('face_detected', False)]
        
        for field in fields:
            # For most fields, only use face-detected frames
            # For break phase, we might want all frames (chaos state)
            values = [d.get(field, 0.0) for d in face_detected_data if field in d]
            
            if values:
                stats[f'avg_{field}'] = float(np.mean(values))
                stats[f'std_{field}'] = float(np.std(values))
            else:
                # Default values if no data
                stats[f'avg_{field}'] = 0.0
                stats[f'std_{field}'] = 0.01  # Small std dev to avoid division by zero
        
        return stats
    
    def save_baseline(self, rating: float):
        """
        Calculate statistics and save baseline via engine.
        
        Args:
            rating: User rating (1-10) from work phase
        """
        if not self.engine:
            raise RuntimeError("Engine not initialized")
        
        if not self.work_data:
            raise ValueError("No work phase data to save")
        
        print(f"\n[Training] Calculating session statistics...")
        
        # Aggregate work phase statistics
        work_stats = self.aggregate_statistics(self.work_data)
        
        print(f"[Training] Work phase statistics:")
        print(f"  Avg blink rate: {work_stats.get('avg_blink_rate', 0):.2f} /min")
        print(f"  Avg PERCLOS: {work_stats.get('avg_perclos', 0):.3f}")
        print(f"  Avg gaze stability: {work_stats.get('avg_gaze_stability', 0):.3f}")
        print(f"  Avg fidgeting: {work_stats.get('avg_fidgeting_score', 0):.3f}")
        
        # Convert aggregated stats to format expected by C++ (StateVector-like dict)
        # The C++ end_calibration_session expects a StateVector with the aggregated values
        session_stats = {
            'blink_rate': work_stats.get('avg_blink_rate', 0.0),
            'perclos': work_stats.get('avg_perclos', 0.0),
            'gaze_stability': work_stats.get('avg_gaze_stability', 0.0),
            'fidgeting_score': work_stats.get('avg_fidgeting_score', 0.0),
        }
        
        # End calibration session (this will update baseline and save profile)
        print(f"\n[Training] Saving baseline with rating: {rating}/10...")
        try:
            self.engine.end_calibration_session(session_stats, rating)
            print(f"[Training] Baseline saved successfully!")
            print(f"[Training] Profile saved to: {self.engine.profile_path}")
        except Exception as e:
            print(f"[ERROR] Failed to save baseline: {e}")
            raise


def main():
    """Main entry point for calibration CLI."""
    parser = argparse.ArgumentParser(
        description="Two-phase calibration for Lock In Labs fatigue detection",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python calibration_cli.py --user tom_pham
  python calibration_cli.py --user tom_pham --work-duration 30 --break-duration 5
        """
    )
    
    parser.add_argument(
        '--user',
        type=str,
        default='default_user',
        help='User identifier (default: default_user)'
    )
    
    parser.add_argument(
        '--work-duration',
        type=int,
        default=30,
        help='Work phase duration in minutes (default: 30)'
    )
    
    parser.add_argument(
        '--break-duration',
        type=int,
        default=5,
        help='Break phase duration in minutes (default: 5)'
    )
    
    parser.add_argument(
        '--camera-index',
        type=int,
        default=0,
        help='Camera device index (default: 0). Use 1, 2, etc. if you have multiple cameras or if camera 0 is in use.'
    )
    
    args = parser.parse_args()
    
    print("\n" + "="*60)
    print("LOCK IN LABS - TWO-PHASE CALIBRATION")
    print("="*60)
    print(f"User: {args.user}")
    print(f"Work Duration: {args.work_duration} minutes")
    print(f"Break Duration: {args.break_duration} minutes")
    print("\nThis will:")
    print("  1. Collect baseline data while you work (Phase 1)")
    print("  2. Ask you to rate your focus level (1-10)")
    print("  3. Collect 'chaos' data while you relax (Phase 2)")
    print("  4. Save your personalized profile")
    print("\nMake sure:")
    if args.camera_index == 0:
        print("  - The fatigue detection daemon (app.py) is NOT running (or use --camera-index 1)")
    else:
        print(f"  - Camera {args.camera_index} is available (app.py can use camera 0)")
    print("  - You have good lighting and are facing the camera")
    print("  - You're ready to work for the full duration")
    print("="*60)
    
    input("\nPress Enter to start calibration (or CTRL+C to cancel)...")
    
    session = TrainingSession(
        user_id=args.user,
        work_duration_min=args.work_duration,
        break_duration_min=args.break_duration,
        camera_index=args.camera_index
    )
    
    try:
        # Initialize
        session.initialize()
        
        # Phase 1: Work
        should_continue = session.run_work_phase()
        
        if not should_continue:
            print("\n[Training] Calibration cancelled or rating too low.")
            return
        
        # Get rating from user (stored during work phase, but we need it here)
        # Actually, we'll prompt again or store it - let me fix this
        # For now, we'll need to get the rating again or store it in the session
        # Actually, looking at the code, run_work_phase returns True/False based on rating
        # But we need the actual rating value. Let me refactor this.
        
        # Phase 2: Break (only if rating was good)
        session.run_break_phase()
        
        # Save baseline with the stored rating
        if session.user_rating is not None:
            session.save_baseline(session.user_rating)
        else:
            print("\n[ERROR] Rating not available. Cannot save baseline.")
            return
        
        print("\n[Training] Calibration complete!")
        print("[Training] You can now restart the daemon (app.py) to use your personalized profile.")
        
    except KeyboardInterrupt:
        print("\n\n[Training] Calibration cancelled by user.")
    except Exception as e:
        print(f"\n\n[ERROR] Calibration failed: {e}")
        import traceback
        traceback.print_exc()
    finally:
        session.cleanup()


if __name__ == "__main__":
    main()
