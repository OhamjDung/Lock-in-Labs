"""
Test script to verify gaze stability decreases during head shaking.

This script captures video, simulates/records head shaking scenarios,
and verifies that gaze_stability metric correctly reflects head movement.
"""

import cv2
import numpy as np
from engine import FatigueEngine
import time
from collections import deque

def analyze_session(video_source=0, duration_seconds=30):
    """
    Capture video and analyze gaze stability during head movement.
    
    Args:
        video_source: 0 for webcam, or path to video file
        duration_seconds: How long to capture
    """
    
    engine = FatigueEngine("test_user")
    
    cap = cv2.VideoCapture(video_source)
    if not cap.isOpened():
        print(f"Error: Could not open video source {video_source}")
        return
    
    # Set camera properties for better frame rate
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_FPS, 30)
    
    print("Gaze Stability Test - Head Shake Detection")
    print("=" * 60)
    print("\nINSTRUCTIONS:")
    print("1. First 5 seconds: Keep your head STILL (baseline)")
    print("2. Next 10 seconds: SHAKE your head VIOLENTLY side-to-side")
    print("3. Next 10 seconds: Keep your head STILL again")
    print("\nPress 'q' to quit early, 'r' to reset, 'p' to pause")
    print("=" * 60)
    
    start_time = time.time()
    frame_count = 0
    gaze_stability_history = deque(maxlen=30)  # Keep last 1 second (30 FPS)
    time_history = deque(maxlen=30)
    
    baseline_stability = None
    shake_stability_min = None
    recovery_stability = None
    
    phase = 0  # 0=baseline, 1=shaking, 2=recovery
    phase_start_time = start_time
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("End of video")
                break
            
            # Process frame
            metrics = engine.process_frame(frame)
            
            current_time = time.time() - start_time
            if current_time > duration_seconds:
                print(f"\nTest duration complete ({duration_seconds}s)")
                break
            
            # Determine current phase
            if current_time < 5:
                current_phase = 0
                phase_name = "BASELINE (keep still)"
            elif current_time < 15:
                current_phase = 1
                phase_name = "SHAKING (shake head!)"
            else:
                current_phase = 2
                phase_name = "RECOVERY (keep still)"
            
            if current_phase != phase:
                phase = current_phase
                phase_start_time = current_time
                print(f"\n--- Phase {current_phase + 1}: {phase_name} ---")
            
            # Track stability
            gaze_stability = metrics.get("gaze_stability", 0.0)
            gaze_stability_history.append(gaze_stability)
            time_history.append(current_time)
            
            # Update phase statistics
            if phase == 0 and baseline_stability is None:
                baseline_stability = gaze_stability
            elif phase == 1:
                if shake_stability_min is None:
                    shake_stability_min = gaze_stability
                else:
                    shake_stability_min = min(shake_stability_min, gaze_stability)
            elif phase == 2 and recovery_stability is None:
                recovery_stability = gaze_stability
            
            # Display current metrics
            frame_count += 1
            if frame_count % 10 == 0:  # Print every ~0.3 seconds
                avg_stability = np.mean(list(gaze_stability_history)) if gaze_stability_history else 0
                print(f"Time: {current_time:5.1f}s | Phase: {phase_name:20s} | "
                      f"Gaze Stability: {gaze_stability:.3f} | "
                      f"Avg (last 1s): {avg_stability:.3f} | "
                      f"Blink Rate: {metrics.get('blink_rate', 0):.1f}")
            
            # Display on frame
            h, w = frame.shape[:2]
            cv2.putText(frame, f"Gaze Stability: {gaze_stability:.3f}", (10, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            cv2.putText(frame, phase_name, (10, 70), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            
            cv2.imshow("Gaze Stability Test", frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                print("\nTest interrupted by user")
                break
            elif key == ord('r'):
                gaze_stability_history.clear()
                time_history.clear()
                baseline_stability = None
                shake_stability_min = None
                recovery_stability = None
                phase = 0
                print("\nReset statistics")
            elif key == ord('p'):
                print("\nPaused - press any key to continue")
                cv2.waitKey(0)
    
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    # Print analysis results
    print("\n" + "=" * 60)
    print("ANALYSIS RESULTS")
    print("=" * 60)
    
    if baseline_stability is not None:
        print(f"Baseline stability (still):  {baseline_stability:.3f}")
    if shake_stability_min is not None:
        print(f"Shake stability (minimum):   {shake_stability_min:.3f}")
    if recovery_stability is not None:
        print(f"Recovery stability (still):  {recovery_stability:.3f}")
    
    # Check if test passed
    print("\nTEST VALIDATION:")
    if baseline_stability is not None and shake_stability_min is not None:
        drop = baseline_stability - shake_stability_min
        drop_percent = (drop / baseline_stability * 100) if baseline_stability > 0 else 0
        print(f"Stability drop during shake: {drop:.3f} ({drop_percent:.1f}%)")
        
        if drop > 0.20:  # Should drop by at least 0.2 points
            print("✓ PASS: Head shaking correctly reduces gaze stability")
        else:
            print("✗ FAIL: Head shaking did not sufficiently reduce gaze stability")
    else:
        print("✗ Incomplete test data")


if __name__ == "__main__":
    import sys
    
    print("Gaze Stability - Head Shake Detection Test")
    print("\nOptions:")
    print("  1. Test with webcam (default)")
    print("  2. Test with video file")
    
    choice = input("Enter choice (1 or 2): ").strip()
    
    if choice == "2":
        video_path = input("Enter video file path: ").strip()
        analyze_session(video_source=video_path, duration_seconds=30)
    else:
        analyze_session(video_source=0, duration_seconds=30)
