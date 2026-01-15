"""
Integration Example: MediaPipe Vision System + C++ Fatigue Engine

This example shows how to use the MediaPipe vision system to extract metrics
and send them to the C++ fatigue engine for processing.
"""

import cv2
import sys
import os
import time

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fatigue_detection.face_tracking import VisionSystem
from fatigue_detection.engine import FatigueEngine

def main():
    print("[MediaPipe + C++ Engine Integration Example]")
    print("=" * 60)
    
    # Check dependencies
    try:
        import mediapipe as mp
        print(f"[OK] MediaPipe version: {mp.__version__}")
    except ImportError:
        print("[ERROR] MediaPipe not installed!")
        print("Install it with: pip install mediapipe")
        return 1
    
    # Initialize vision system (Python - MediaPipe)
    print("\n[Initializing Vision System (MediaPipe)...]")
    vision = VisionSystem(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    print("[OK] Vision system ready")
    
    # Initialize C++ fatigue engine
    print("\n[Initializing C++ Fatigue Engine...]")
    try:
        engine = FatigueEngine(user_id="test_user")
        print("[OK] C++ engine ready")
    except Exception as e:
        print(f"[ERROR] Failed to initialize C++ engine: {e}")
        return 1
    
    # Open camera
    print("\n[Opening camera...]")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera")
        return 1
    
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("[OK] Camera opened")
    
    print("\n[Starting hybrid processing...]")
    print("Press 'q' to quit")
    print("\nFlow: Camera -> MediaPipe (Python) -> Metrics -> C++ Engine -> Fatigue Score")
    
    frame_count = 0
    start_time = time.time()
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            
            frame_count += 1
            timestamp_ms = int(time.time() * 1000)
            
            # Step 1: Process frame with MediaPipe (Python)
            vision_results = vision.process(frame)
            
            if vision_results["face_detected"]:
                # Step 2: Extract metrics from MediaPipe
                ear = vision_results["ear"]
                mar = vision_results["mar"]
                gaze_x = vision_results["gaze_x"]
                gaze_y = vision_results["gaze_y"]
                
                # Step 3: Send metrics to C++ engine
                # NOTE: The C++ engine's process_frame() currently expects a cv::Mat.
                # For full integration, we need to update the C++ engine to accept
                # metrics directly (update_metrics(ear, mar, gaze_x, gaze_y)).
                # 
                # For now, we can still use process_frame() but MediaPipe will be
                # more stable than the internal Dlib detection.
                
                # Option A: Use C++ engine's process_frame (still uses Dlib internally)
                # This is a temporary solution until C++ is updated
                metrics = engine.process_frame(frame, timestamp_ms)
                
                # Option B: Future - Direct metric update (requires C++ changes)
                # metrics = engine.update_metrics(
                #     ear=ear,
                #     mar=mar,
                #     gaze_x=gaze_x,
                #     gaze_y=gaze_y,
                #     timestamp_ms=timestamp_ms
                # )
                
                # Display results
                y_pos = 30
                cv2.putText(frame, f"MediaPipe EAR: {ear:.3f}", (10, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                y_pos += 20
                cv2.putText(frame, f"MediaPipe MAR: {mar:.3f}", (10, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                y_pos += 20
                cv2.putText(frame, f"C++ Fatigue: {metrics.get('fatigue_score', 0):.2f}", 
                           (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                y_pos += 20
                cv2.putText(frame, f"Level: {metrics.get('fatigue_level', 'N/A')}", 
                           (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
                
                # Draw bounding box
                if vision_results.get("face_bbox"):
                    x, y, w, h = vision_results["face_bbox"]
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            else:
                cv2.putText(frame, "No face detected", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Calculate FPS
            elapsed = time.time() - start_time
            fps = frame_count / elapsed if elapsed > 0 else 0
            cv2.putText(frame, f"FPS: {fps:.1f}", (10, frame.shape[0] - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            cv2.imshow("MediaPipe + C++ Engine", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
    
    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
    finally:
        print("\n[Cleaning up...]")
        vision.release()
        cap.release()
        cv2.destroyAllWindows()
        print("[OK] Integration test complete")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
