#!/usr/bin/env python
"""
Blink Detection Calibration Tool.

This script helps calibrate the Eye Aspect Ratio (EAR) threshold for your specific eye shape.
It measures your EAR when eyes are open vs closed, then sets a personalized threshold.
"""

import cv2
import numpy as np
import os
import sys
import json
import time

# Add project root to path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from fatigue_detection.engine import FatigueEngine

def calibrate_blink_threshold(user_id: str = "default_user", duration_sec: int = 30):
    """
    Calibrate blink detection by measuring EAR values.
    
    Instructions:
    1. Sit in front of camera
    2. Keep eyes OPEN for 10 seconds
    3. Then CLOSE eyes for 5 seconds
    4. Repeat 2-3 times
    """
    print("=" * 60)
    print("BLINK DETECTION CALIBRATION")
    print("=" * 60)
    print(f"\nUser: {user_id}")
    print(f"Duration: {duration_sec} seconds")
    print("\nInstructions:")
    print("1. Sit in front of the camera with good lighting")
    print("2. Keep your eyes OPEN for 10 seconds")
    print("3. Then CLOSE your eyes for 5 seconds")
    print("4. Repeat 2-3 times")
    print("\nPress 'q' to quit, 's' to start/stop recording")
    print("=" * 60)
    
    # Initialize camera
    camera = cv2.VideoCapture(0)
    if not camera.isOpened():
        print("ERROR: Failed to open camera")
        return None
    
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Initialize engine
    try:
        os.chdir(current_dir)  # Change to fatigue_detection directory
        engine = FatigueEngine(user_id)
        os.chdir(parent_dir)  # Restore
    except Exception as e:
        print(f"ERROR: Failed to initialize engine: {e}")
        camera.release()
        return None
    
    # Storage for EAR values
    ear_values_open = []
    ear_values_closed = []
    recording = False
    start_time = None
    
    window_name = "Blink Calibration - Press 's' to start, 'q' to quit"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    
    print("\nPress 's' to start recording...")
    
    frame_count = 0
    while True:
        ret, frame = camera.read()
        if not ret:
            continue
        
        # Process frame
        timestamp_ms = int(time.time() * 1000)
        try:
            metrics = engine.process_frame(frame, timestamp_ms)
            
            # Get EAR from metrics (now exposed from C++)
            current_ear = metrics.get("current_ear", 0.0)
            blink_rate = metrics.get("blink_rate", 0.0)
            perclos = metrics.get("perclos", 0.0)
            face_detected = metrics.get("face_detected", False)
            
            # Display instructions
            h, w = frame.shape[:2]
            overlay = frame.copy()
            cv2.rectangle(overlay, (10, 10), (w - 10, 200), (0, 0, 0), -1)
            cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
            
            y_pos = 40
            font = cv2.FONT_HERSHEY_SIMPLEX
            
            if not face_detected:
                cv2.putText(frame, "NO FACE DETECTED - Move closer!", (20, y_pos),
                           font, 0.8, (0, 0, 255), 2)
            else:
                if not recording:
                    cv2.putText(frame, "Press 's' to START recording", (20, y_pos),
                               font, 0.7, (0, 255, 0), 2)
                    y_pos += 40
                    cv2.putText(frame, "Then: OPEN eyes 10s, CLOSE 5s, repeat", (20, y_pos),
                               font, 0.6, (255, 255, 255), 1)
                else:
                    elapsed = int(time.time() - start_time)
                    remaining = duration_sec - elapsed
                    cv2.putText(frame, f"RECORDING... {elapsed}/{duration_sec}s", (20, y_pos),
                               font, 0.7, (0, 255, 255), 2)
                    y_pos += 40
                    
                    if elapsed < duration_sec:
                        if elapsed % 15 < 10:  # First 10 seconds of each 15-second cycle
                            cv2.putText(frame, "KEEP EYES OPEN", (20, y_pos),
                                       font, 0.8, (0, 255, 0), 2)
                            # Store EAR when eyes are open
                            if current_ear > 0 and perclos < 0.1:  # Eyes mostly open
                                ear_values_open.append(current_ear)
                        else:
                            cv2.putText(frame, "CLOSE YOUR EYES", (20, y_pos),
                                       font, 0.8, (0, 0, 255), 2)
                            # Store EAR when eyes are closed
                            if current_ear > 0 and perclos > 0.5:  # Eyes mostly closed
                                ear_values_closed.append(current_ear)
                    else:
                        cv2.putText(frame, "Recording complete! Press 'q' to save", (20, y_pos),
                                   font, 0.6, (0, 255, 255), 2)
            
            # Show current metrics
            y_pos = 250
            if current_ear > 0:
                cv2.putText(frame, f"Current EAR: {current_ear:.3f}", (20, y_pos),
                           font, 0.6, (255, 255, 0), 2)
                y_pos += 30
            cv2.putText(frame, f"Blink Rate: {blink_rate:.1f}/min", (20, y_pos),
                       font, 0.5, (255, 255, 255), 1)
            y_pos += 25
            cv2.putText(frame, f"PERCLOS: {perclos:.2f}", (20, y_pos),
                       font, 0.5, (255, 255, 255), 1)
            y_pos += 25
            cv2.putText(frame, f"Open samples: {len(ear_values_open)}", (20, y_pos),
                       font, 0.5, (255, 255, 255), 1)
            y_pos += 25
            cv2.putText(frame, f"Closed samples: {len(ear_values_closed)}", (20, y_pos),
                       font, 0.5, (255, 255, 255), 1)
            
        except Exception as e:
            print(f"Error processing frame: {e}")
        
        cv2.imshow(window_name, frame)
        
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            break
        elif key == ord('s'):
            if not recording:
                recording = True
                start_time = time.time()
                print("\n[RECORDING] Follow the on-screen instructions...")
            else:
                recording = False
                print("\n[PAUSED] Press 's' to resume or 'q' to finish")
        
        frame_count += 1
    
    camera.release()
    cv2.destroyAllWindows()
    
    # Calculate calibration
    if len(ear_values_open) > 10 and len(ear_values_closed) > 10:
        avg_open = np.mean(ear_values_open)
        avg_closed = np.mean(ear_values_closed)
        threshold = (avg_open + avg_closed) / 2.0
        
        print("\n" + "=" * 60)
        print("CALIBRATION RESULTS")
        print("=" * 60)
        print(f"Average EAR (eyes open): {avg_open:.3f}")
        print(f"Average EAR (eyes closed): {avg_closed:.3f}")
        print(f"Recommended threshold: {threshold:.3f}")
        print(f"\nCurrent hardcoded threshold: 0.25")
        print(f"Your personalized threshold: {threshold:.3f}")
        print("\nNote: Update EAR_THRESHOLD in gaze_detector.h to use this value.")
        print("=" * 60)
        
        # Save calibration
        calib_data = {
            "user_id": user_id,
            "ear_open_avg": float(avg_open),
            "ear_closed_avg": float(avg_closed),
            "recommended_threshold": float(threshold),
            "current_hardcoded_threshold": 0.25,
            "timestamp": time.time()
        }
        
        calib_path = os.path.join(current_dir, "profiles", f"{user_id}_blink_calibration.json")
        os.makedirs(os.path.dirname(calib_path), exist_ok=True)
        
        with open(calib_path, 'w') as f:
            json.dump(calib_data, f, indent=2)
        
        print(f"\nCalibration saved to: {calib_path}")
        return calib_data
    else:
        print("\nERROR: Not enough samples collected!")
        print(f"Need at least 10 samples each. Got: {len(ear_values_open)} open, {len(ear_values_closed)} closed")
        return None


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Calibrate blink detection threshold")
    parser.add_argument("--user", default="default_user", help="User ID")
    parser.add_argument("--duration", type=int, default=30, help="Calibration duration in seconds")
    args = parser.parse_args()
    
    calibrate_blink_threshold(args.user, args.duration)
