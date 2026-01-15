"""
Test script for MediaPipe Vision System.
Run this to verify the face tracking system works correctly.
"""

import cv2
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from fatigue_detection.face_tracking import VisionSystem

def main():
    print("[MediaPipe Vision System Test]")
    print("=" * 50)
    
    # Check if MediaPipe is installed
    try:
        import mediapipe as mp
        print(f"[OK] MediaPipe version: {mp.__version__}")
    except ImportError:
        print("[ERROR] MediaPipe not installed!")
        print("Install it with: pip install mediapipe")
        return 1
    
    # Initialize vision system
    print("\n[Initializing Vision System...]")
    vision = VisionSystem(
        max_num_faces=1,
        refine_landmarks=True,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5
    )
    print("[OK] Vision system initialized")
    
    # Open camera
    print("\n[Opening camera...]")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera")
        return 1
    
    # Set camera resolution
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    print("[OK] Camera opened (640x480)")
    
    print("\n[Starting face tracking...]")
    print("Press 'q' to quit, 'd' to toggle landmark drawing")
    
    draw_landmarks = False
    frame_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[ERROR] Failed to read frame")
                break
            
            frame_count += 1
            
            # Process frame
            results = vision.process(frame)
            
            # Draw landmarks if enabled
            if draw_landmarks and results["face_detected"]:
                frame = vision.draw_landmarks(frame, results)
            elif results["face_detected"]:
                # Draw simple bounding box
                if results.get("face_bbox"):
                    x, y, w, h = results["face_bbox"]
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                
                # Draw metrics
                y_pos = 30
                cv2.putText(frame, f"EAR: {results['ear']:.3f}", (10, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                y_pos += 25
                cv2.putText(frame, f"MAR: {results['mar']:.3f}", (10, y_pos), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                y_pos += 25
                cv2.putText(frame, f"Gaze: ({results['gaze_x']:.2f}, {results['gaze_y']:.2f})", 
                           (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "No face detected", (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Draw FPS
            cv2.putText(frame, f"FPS: {frame_count}", (10, frame.shape[0] - 20), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Show frame
            cv2.imshow("MediaPipe Face Tracking Test", frame)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('d'):
                draw_landmarks = not draw_landmarks
                print(f"[DEBUG] Landmark drawing: {'ON' if draw_landmarks else 'OFF'}")
    
    except KeyboardInterrupt:
        print("\n[Interrupted by user]")
    finally:
        print("\n[Cleaning up...]")
        vision.release()
        cap.release()
        cv2.destroyAllWindows()
        print("[OK] Test complete")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
