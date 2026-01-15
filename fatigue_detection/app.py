"""
Fatigue Detection Daemon Server.
Python owns the camera, processes frames with C++ engine, sends metrics via WebSocket.
"""

import cv2
import asyncio
import json
import time
import random
import os
import sys
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict

# IMPORTANT: Ensure we're using system Python, not MSYS2 Python
# Check if we're using MSYS2 Python (which won't have our dependencies)
if "msys64" in sys.executable.lower() or "mingw" in sys.executable.lower():
    print("WARNING: Detected MSYS2 Python. The module was built for system Python.")
    print(f"Current Python: {sys.executable}")
    print("Please run with system Python:")
    print("  C:\\Users\\ohamj\\AppData\\Local\\Programs\\Python\\Python313\\python.exe app.py")
    print("Or remove MSYS2 from PATH temporarily.")
    # sys.exit(1)  # Comment out to allow MSYS2 Python for testing

# Add MSYS2 bin to PATH for DLL dependencies (must be before importing engine)
# But do it AFTER checking which Python we're using
msys2_bin = r"C:\msys64\ucrt64\bin"
if os.path.exists(msys2_bin):
    # Prepend to PATH (don't append, to avoid MSYS2 Python being found first)
    current_path = os.environ.get("PATH", "")
    if msys2_bin not in current_path:
        os.environ["PATH"] = msys2_bin + os.pathsep + current_path

# Add project root to Python path (required for importing fatigue_detection.engine)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # Project root
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

import numpy as np
from fatigue_detection.engine import FatigueEngine
from fatigue_detection.face_tracking import VisionSystem
from fatigue_detection.pvt_challenge import PVTChallenge, interpret_reaction_time
from fatigue_detection.notification_manager import get_notification_manager
from fatigue_detection.window_tracker import WindowTracker
from fatigue_detection.screen_geometry import ScreenGeometry

# Global: Python owns the camera
camera: Optional[cv2.VideoCapture] = None
engine: Optional[FatigueEngine] = None
vision_system: Optional[VisionSystem] = None  # MediaPipe vision system
window_tracker: Optional[WindowTracker] = None  # Gate 1: Context tracking
screen_geometry: Optional[ScreenGeometry] = None  # Gate 2: Focus tracking
active_connections: set = set()  # Track active WebSocket connections
show_camera_window: bool = True  # Toggle camera display window
latest_metrics: Optional[dict] = None  # Latest metrics for display
metrics_lock = threading.Lock()  # Thread-safe access to metrics
pvt_challenges: dict = {}  # Per-connection PVT challenge state {websocket: PVTChallenge}
pvt_lock = threading.Lock()  # Thread-safe access to PVT challenges
pvt_display_state: dict = {"active": False, "message": "", "trigger_time": 0}  # Shared state for camera display
pvt_display_lock = threading.Lock()  # Thread-safe access to PVT display state

# Head position tracking for stillness detection
head_position_history = []  # List of (pitch, yaw, roll) tuples
max_head_history = 30  # Track last 30 frames (~1 second at 30fps)

# Gaze position tracking for reading vs zoning detection
gaze_position_history = []  # List of (gaze_x, gaze_y) tuples
max_gaze_history = 30  # Track last 30 frames

# Manual landmark offsets (for fine-tuning alignment)
# Separate offsets for eyes and mouth
eye_offset_x = 0.0
eye_offset_y = 0.0
mouth_offset_x = 0.0
mouth_offset_y = 0.0
# Legacy combined offset
offset_x = 0.0
offset_y = 0.0
offset_lock = threading.Lock()  # Thread-safe access to offsets


def initialize_camera(user_id: str = "default_user", camera_index: int = 0):
    """Initialize camera, engine, and MediaPipe vision system."""
    global camera, engine, vision_system, window_tracker, screen_geometry
    
    print(f"[INFO] Initializing camera and engine for user: {user_id}")
    
    # Open camera
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError(f"Failed to open camera {camera_index}")
    
    # Set camera properties (optional, for performance)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
    # Use lower resolution to reduce memory usage (640x480 = ~0.9MB vs 1280x720 = ~2.6MB per frame)
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)  # Reduced from 1280 to save memory
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)  # Reduced from 720 to save memory
    
    # Get actual camera resolution (might be different from requested)
    actual_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Camera opened: {actual_width}x{actual_height}")
    
    # Initialize MediaPipe vision system
    print("[INFO] Initializing MediaPipe vision system...")
    try:
        vision_system = VisionSystem(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        print("[OK] MediaPipe vision system initialized")
    except Exception as e:
        print(f"[ERROR] Failed to initialize MediaPipe vision system: {e}")
        raise
    
    # Initialize THREE-GATE SYSTEM
    print("[INFO] Initializing three-gate tracking system...")
    try:
        # Gate 1: Context tracking (active window)
        window_tracker = WindowTracker(poll_interval=2.0)
        print("[OK] Window tracker initialized (Gate 1)")
        
        # Gate 2: Focus tracking (screen boundaries)
        screen_geometry = ScreenGeometry(tolerance=0.15)
        print("[OK] Screen geometry initialized (Gate 2)")
    except Exception as e:
        print(f"[WARN] Failed to initialize gate trackers: {e}")
        # Non-fatal, can continue with basic fatigue detection
    
    # Initialize C++ engine
    try:
        # Ensure we're in the right directory for model loading
        current_dir = os.path.dirname(os.path.abspath(__file__))
        original_dir = os.getcwd()
        
        # Change to fatigue_detection directory so model path is relative
        os.chdir(current_dir)
        
        engine = FatigueEngine(user_id)
        
        # Restore original directory
        os.chdir(original_dir)
        
        print(f"[INFO] Camera and engine initialized successfully")
    except Exception as e:
        camera.release()
        import traceback
        traceback.print_exc()
        raise RuntimeError(f"Failed to initialize engine: {e}") from e


def display_camera_loop():
    """Thread function to display camera feed with metrics overlay."""
    global camera, engine, vision_system, show_camera_window, latest_metrics
    
    window_name = "Fatigue Detection - Camera Feed"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 1280, 720)
    
    print("[INFO] Camera display window opened. Press 'q' in window to close.")
    print("[INFO] Make sure you're sitting in front of the camera with good lighting!")
    
    frame_skip = 0  # Skip some frames for display (process every Nth frame)
    current_metrics = {}  # Initialize with empty metrics
    
    while show_camera_window:
        if camera is None or engine is None:
            # Create blank frame with message
            blank = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(blank, "Camera not initialized", (50, 240), 
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
            cv2.imshow(window_name, blank)
        else:
            ret, frame = camera.read()
            if not ret:
                time.sleep(0.033)  # Wait if frame read fails
                continue
            
            h, w = frame.shape[:2]  # Get frame dimensions for overlay
            
            # Use latest metrics if available (updated by WebSocket loop or this loop)
            with metrics_lock:
                if latest_metrics:
                    current_metrics = latest_metrics.copy()
            
            # Process frame for display
            if frame_skip % 2 == 0:  # Process every other frame for display (save CPU)
                try:
                    timestamp_ms = int(time.time() * 1000)
                    # Process frame with MediaPipe vision system
                    vision_results = vision_system.process(frame)
                    
                    # Calculate gate multipliers (same logic as WebSocket loop)
                    active_window_title = "Unknown"
                    context_multiplier = 0.5
                    if window_tracker:
                        try:
                            active_window_title, context_multiplier = window_tracker.get_active_window()
                        except:
                            pass
                    
                    looking_at_screen = False
                    focus_multiplier = 0.0
                    phone_detected = False
                    if screen_geometry and vision_results and vision_results.get("face_detected"):
                        gaze_x = vision_results.get("gaze_x", 0.0)
                        gaze_y = vision_results.get("gaze_y", 0.0)
                        looking_at_screen = screen_geometry.is_looking_at_screen(gaze_x, gaze_y)
                        focus_multiplier = screen_geometry.get_focus_multiplier(gaze_x, gaze_y, phone_detected)
                    
                    if vision_results and vision_results.get("face_detected"):
                        # Update C++ engine with MediaPipe metrics
                        metrics = engine.update_metrics(
                            ear=vision_results["ear"],
                            mar=vision_results["mar"],
                            gaze_x=vision_results["gaze_x"],
                            gaze_y=vision_results["gaze_y"],
                            timestamp_ms=timestamp_ms,
                            face_detected=True,
                            head_pitch=vision_results.get("head_pitch", 0.0),
                            head_yaw=vision_results.get("head_yaw", 0.0),
                            head_roll=vision_results.get("head_roll", 0.0)
                        )
                        
                        # Add gate multipliers
                        metrics["active_window"] = active_window_title
                        metrics["context_multiplier"] = context_multiplier
                        metrics["looking_at_screen"] = looking_at_screen
                        metrics["phone_detected"] = phone_detected
                        metrics["focus_multiplier"] = focus_multiplier
                        fatigue_score = metrics.get("fatigue_score", 0.0)
                        fatigue_multiplier = 1.0 - fatigue_score
                        lock_in_score = context_multiplier * focus_multiplier * fatigue_multiplier
                        metrics["fatigue_multiplier"] = fatigue_multiplier
                        metrics["lock_in_score"] = lock_in_score
                        # Add MediaPipe face bbox to metrics for display
                        if vision_results.get("face_bbox"):
                            x, y, w, h = vision_results["face_bbox"]
                            metrics["face_bbox"] = {"x": x, "y": y, "width": w, "height": h}
                            metrics["face_detected"] = True
                            metrics["scale_factor"] = 1.0  # MediaPipe uses original frame, no scaling
                        
                        # Extract MediaPipe landmarks for display
                        if vision_results.get("landmarks"):
                            landmarks = vision_results["landmarks"]
                            h_frame, w_frame = frame.shape[:2]
                            
                            # MediaPipe landmark indices for eyes and mouth
                            # Left eye: 33, 7, 163, 144, 145, 153, 154, 155, 133, 173, 157, 158, 159, 160, 161, 246
                            # Right eye: 362, 382, 381, 380, 374, 373, 390, 249, 263, 466, 388, 387, 386, 385, 384, 398
                            # Mouth: 61, 146, 91, 181, 84, 17, 314, 405, 320, 307, 375, 321, 308, 324, 318
                            # Nose tip: 1
                            
                            # Left eye (simplified - use 6 key points: corners and top/bottom)
                            left_eye_indices = [33, 133, 157, 158, 159, 160]  # Simplified set
                            left_eye_points = []
                            for idx in left_eye_indices:
                                if idx < len(landmarks):
                                    pt = landmarks[idx]
                                    left_eye_points.extend([pt.x * w_frame, pt.y * h_frame])
                            
                            # Right eye (simplified)
                            right_eye_indices = [362, 263, 387, 388, 389, 390]  # Simplified set
                            right_eye_points = []
                            for idx in right_eye_indices:
                                if idx < len(landmarks):
                                    pt = landmarks[idx]
                                    right_eye_points.extend([pt.x * w_frame, pt.y * h_frame])
                            
                            # Mouth (use key points: corners and top/bottom)
                            mouth_indices = [61, 291, 39, 181, 0, 17, 269, 405, 13, 14]  # Key mouth points
                            mouth_points = []
                            for idx in mouth_indices:
                                if idx < len(landmarks):
                                    pt = landmarks[idx]
                                    mouth_points.extend([pt.x * w_frame, pt.y * h_frame])
                            
                            # Nose tip
                            nose_tip = []
                            if 1 < len(landmarks):
                                pt = landmarks[1]
                                nose_tip = [pt.x * w_frame, pt.y * h_frame]
                            
                            metrics["left_eye_points"] = left_eye_points
                            metrics["right_eye_points"] = right_eye_points
                            metrics["mouth_points"] = mouth_points
                            metrics["nose_tip"] = nose_tip
                            
                            # Add gaze and head pose angles for display
                            metrics["gaze_x"] = vision_results.get("gaze_x", 0.0)
                            metrics["gaze_y"] = vision_results.get("gaze_y", 0.0)
                            metrics["head_pitch"] = vision_results.get("head_pitch", 0.0)
                            metrics["head_yaw"] = vision_results.get("head_yaw", 0.0)
                            metrics["head_roll"] = vision_results.get("head_roll", 0.0)
                            metrics["mar_raw"] = vision_results.get("mar", 0.0)  # Debug: show raw MAR
                    else:
                        # No face detected
                        metrics = engine.update_metrics(
                            ear=0.0,
                            mar=0.0,
                            gaze_x=0.0,
                            gaze_y=0.0,
                            timestamp_ms=timestamp_ms,
                            face_detected=False
                        )
                        metrics["face_detected"] = False
                        metrics["face_bbox"] = {"x": 0, "y": 0, "width": 0, "height": 0}
                        
                        # Add gate multipliers (zeros for no face)
                        metrics["active_window"] = active_window_title
                        metrics["context_multiplier"] = context_multiplier
                        metrics["looking_at_screen"] = False
                        metrics["phone_detected"] = False
                        metrics["focus_multiplier"] = 0.0
                        metrics["fatigue_multiplier"] = 0.0
                        metrics["lock_in_score"] = 0.0
                    
                    current_metrics = metrics
                    
                    # Update latest metrics (thread-safe)
                    with metrics_lock:
                        latest_metrics = metrics
                except Exception as e:
                    print(f"[ERROR] Display loop processing error: {e}")
                    # Create dummy metrics on error
                    current_metrics = {"face_detected": False, "fatigue_score": 0.0}
            
            frame_skip += 1
            
            # Draw metrics overlay on frame (avoid copying if possible)
            try:
                # Only copy frame if we need to draw overlay (to save memory)
                frame_to_display = frame.copy() if show_camera_window else frame
                frame_with_overlay = draw_metrics_overlay(frame_to_display, current_metrics, engine)
                
                # Draw face detection indicator directly on frame (visual feedback)
                if current_metrics.get("face_detected", False):
                    cv2.putText(frame_with_overlay, "FACE DETECTED", (w - 200, 30),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                else:
                    cv2.putText(frame_with_overlay, "NO FACE", (w - 150, 30),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                    # Show hint text
                    cv2.putText(frame_with_overlay, "Move closer / Face camera", (w - 250, h - 20),
                              cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
                
                cv2.imshow(window_name, frame_with_overlay)
            except Exception as e:
                print(f"[ERROR] Display overlay error: {e}")
                cv2.imshow(window_name, frame)
        
        # Check for key press (non-blocking)
        key = cv2.waitKey(1) & 0xFF
        global offset_x, offset_y, eye_offset_x, eye_offset_y, mouth_offset_x, mouth_offset_y
        
        if key == ord('q') or key == 27:  # 'q' or ESC
            print("[INFO] Camera window closed by user (press 'q' or ESC)")
            show_camera_window = False
            break
        # Eye offsets (WASD - lowercase for eyes)
        elif key == ord('w'):  # 'w' - move eyes up
            with offset_lock:
                eye_offset_y -= 1.0
            if engine:
                engine.set_eye_offset(eye_offset_x, eye_offset_y)
            print(f"[EYE OFFSET] Y -= 1.0  (Current: X={eye_offset_x:.1f}, Y={eye_offset_y:.1f})")
        elif key == ord('s'):  # 's' - move eyes down
            with offset_lock:
                eye_offset_y += 1.0
            if engine:
                engine.set_eye_offset(eye_offset_x, eye_offset_y)
            print(f"[EYE OFFSET] Y += 1.0  (Current: X={eye_offset_x:.1f}, Y={eye_offset_y:.1f})")
        elif key == ord('a'):  # 'a' - move eyes left
            with offset_lock:
                eye_offset_x -= 1.0
            if engine:
                engine.set_eye_offset(eye_offset_x, eye_offset_y)
            print(f"[EYE OFFSET] X -= 1.0  (Current: X={eye_offset_x:.1f}, Y={eye_offset_y:.1f})")
        elif key == ord('d'):  # 'd' - move eyes right
            with offset_lock:
                eye_offset_x += 1.0
            if engine:
                engine.set_eye_offset(eye_offset_x, eye_offset_y)
            print(f"[EYE OFFSET] X += 1.0  (Current: X={eye_offset_x:.1f}, Y={eye_offset_y:.1f})")
        # Mouth offsets (IJKL)
        elif key == ord('i') or key == ord('I'):  # 'i' - move mouth up
            with offset_lock:
                mouth_offset_y -= 1.0
            if engine:
                engine.set_mouth_offset(mouth_offset_x, mouth_offset_y)
            print(f"[MOUTH OFFSET] Y -= 1.0  (Current: X={mouth_offset_x:.1f}, Y={mouth_offset_y:.1f})")
        elif key == ord('k') or key == ord('K'):  # 'k' - move mouth down
            with offset_lock:
                mouth_offset_y += 1.0
            if engine:
                engine.set_mouth_offset(mouth_offset_x, mouth_offset_y)
            print(f"[MOUTH OFFSET] Y += 1.0  (Current: X={mouth_offset_x:.1f}, Y={mouth_offset_y:.1f})")
        elif key == ord('j') or key == ord('J'):  # 'j' - move mouth left
            with offset_lock:
                mouth_offset_x -= 1.0
            if engine:
                engine.set_mouth_offset(mouth_offset_x, mouth_offset_y)
            print(f"[MOUTH OFFSET] X -= 1.0  (Current: X={mouth_offset_x:.1f}, Y={mouth_offset_y:.1f})")
        elif key == ord('l') or key == ord('L'):  # 'l' - move mouth right
            with offset_lock:
                mouth_offset_x += 1.0
            if engine:
                engine.set_mouth_offset(mouth_offset_x, mouth_offset_y)
            print(f"[MOUTH OFFSET] X += 1.0  (Current: X={mouth_offset_x:.1f}, Y={mouth_offset_y:.1f})")
        # False positive feedback for neck crack detection
        elif key == ord('f') or key == ord('F'):  # 'f' - false positive, increase thresholds
            if engine:
                thresholds = engine.adjust_neck_crack_thresholds(velocity_multiplier=1.15, acceleration_multiplier=1.15)
                print(f"[FALSE POSITIVE] Neck crack thresholds increased by 15%")
                print(f"  New thresholds: velocity={thresholds['velocity']:.2f}, acceleration={thresholds['acceleration']:.2f}")
            else:
                print("[ERROR] Engine not initialized")
        # Gaze calibration buttons
        elif key == ord('1'):  # '1' - calibrate LEFT
            if vision_system and current_metrics.get("face_detected"):
                vision_results = vision_system.process(frame)
                if vision_results and vision_results.get("face_detected") and "raw_gaze_x" in vision_results:
                    raw_gaze_x = vision_results["raw_gaze_x"]
                    raw_gaze_y = vision_results["raw_gaze_y"]
                    vision_system.calibrate_gaze("left", raw_gaze_x, raw_gaze_y)
                    cal = vision_system.get_gaze_calibration()
                    print(f"[CALIBRATION] LEFT captured: raw_x={raw_gaze_x:.3f}, raw_y={raw_gaze_y:.3f}")
                    print(f"  Calibration: X=[{cal['gaze_x_min']:.3f}, {cal['gaze_x_max']:.3f}], Y=[{cal['gaze_y_min']:.3f}, {cal['gaze_y_max']:.3f}], Active={cal['calibrated']}")
        elif key == ord('2'):  # '2' - calibrate RIGHT
            if vision_system and current_metrics.get("face_detected"):
                vision_results = vision_system.process(frame)
                if vision_results and vision_results.get("face_detected") and "raw_gaze_x" in vision_results:
                    raw_gaze_x = vision_results["raw_gaze_x"]
                    raw_gaze_y = vision_results["raw_gaze_y"]
                    vision_system.calibrate_gaze("right", raw_gaze_x, raw_gaze_y)
                    cal = vision_system.get_gaze_calibration()
                    print(f"[CALIBRATION] RIGHT captured: raw_x={raw_gaze_x:.3f}, raw_y={raw_gaze_y:.3f}")
                    print(f"  Calibration: X=[{cal['gaze_x_min']:.3f}, {cal['gaze_x_max']:.3f}], Y=[{cal['gaze_y_min']:.3f}, {cal['gaze_y_max']:.3f}], Active={cal['calibrated']}")
        elif key == ord('3'):  # '3' - calibrate UP
            if vision_system and current_metrics.get("face_detected"):
                vision_results = vision_system.process(frame)
                if vision_results and vision_results.get("face_detected") and "raw_gaze_x" in vision_results:
                    raw_gaze_x = vision_results["raw_gaze_x"]
                    raw_gaze_y = vision_results["raw_gaze_y"]
                    vision_system.calibrate_gaze("up", raw_gaze_x, raw_gaze_y)
                    cal = vision_system.get_gaze_calibration()
                    print(f"[CALIBRATION] UP captured: raw_x={raw_gaze_x:.3f}, raw_y={raw_gaze_y:.3f}")
                    print(f"  Calibration: X=[{cal['gaze_x_min']:.3f}, {cal['gaze_x_max']:.3f}], Y=[{cal['gaze_y_min']:.3f}, {cal['gaze_y_max']:.3f}], Active={cal['calibrated']}")
        elif key == ord('4'):  # '4' - calibrate DOWN
            if vision_system and current_metrics.get("face_detected"):
                vision_results = vision_system.process(frame)
                if vision_results and vision_results.get("face_detected") and "raw_gaze_x" in vision_results:
                    raw_gaze_x = vision_results["raw_gaze_x"]
                    raw_gaze_y = vision_results["raw_gaze_y"]
                    vision_system.calibrate_gaze("down", raw_gaze_x, raw_gaze_y)
                    cal = vision_system.get_gaze_calibration()
                    print(f"[CALIBRATION] DOWN captured: raw_x={raw_gaze_x:.3f}, raw_y={raw_gaze_y:.3f}")
                    print(f"  Calibration: X=[{cal['gaze_x_min']:.3f}, {cal['gaze_x_max']:.3f}], Y=[{cal['gaze_y_min']:.3f}, {cal['gaze_y_max']:.3f}], Active={cal['calibrated']}")
        elif key == ord('0'):  # '0' - reset calibration
            if vision_system:
                vision_system.reset_gaze_calibration()
                print("[CALIBRATION] Gaze calibration reset to defaults")
        elif key == ord('r') or key == ord('R'):  # 'r' - reset all offsets
            with offset_lock:
                offset_x = 0.0
                offset_y = 0.0
                eye_offset_x = 0.0
                eye_offset_y = 0.0
                mouth_offset_x = 0.0
                mouth_offset_y = 0.0
            if engine:
                engine.set_landmark_offset(offset_x, offset_y)
                engine.set_eye_offset(eye_offset_x, eye_offset_y)
                engine.set_mouth_offset(mouth_offset_x, mouth_offset_y)
            print(f"[OFFSET] All offsets reset to (0, 0)")
        elif key == ord('c') or key == ord('C'):  # 'c' for eyes closed calibration
            if engine and current_metrics.get("face_detected", False):
                current_ear = current_metrics.get("current_ear", 0.0)
                if current_ear > 0:
                    # Set threshold to slightly below current EAR (eyes closed)
                    new_threshold = max(0.05, current_ear * 0.9)  # 90% of closed EAR
                    try:
                        engine.set_ear_threshold(new_threshold)
                        print(f"[CALIBRATION] EAR threshold set to {new_threshold:.3f} (eyes closed: {current_ear:.3f})")
                        # Show confirmation on screen (store in metrics for display)
                        with metrics_lock:
                            latest_metrics["calibration_message"] = f"EAR calibrated: {new_threshold:.3f}"
                            latest_metrics["calibration_time"] = time.time()
                            current_metrics["calibration_message"] = latest_metrics["calibration_message"]
                            current_metrics["calibration_time"] = latest_metrics["calibration_time"]
                    except Exception as e:
                        print(f"[ERROR] Failed to set EAR threshold: {e}")
                else:
                    print("[WARNING] Cannot calibrate: No EAR value available (face not detected?)")
        elif key == ord('y') or key == ord('Y'):  # 'y' for yawn calibration
            if engine and current_metrics.get("face_detected", False):
                current_mar = current_metrics.get("current_mar", 0.0)
                if current_mar > 0:
                    # Set threshold to slightly below current MAR (mouth open during yawn)
                    # For yawn, we want to detect when MAR exceeds this threshold
                    new_threshold = max(0.20, current_mar * 0.85)  # 85% of yawn MAR
                    try:
                        engine.set_mar_threshold(new_threshold)
                        print(f"[CALIBRATION] MAR threshold set to {new_threshold:.3f} (mouth open: {current_mar:.3f})")
                        # Show confirmation on screen
                        with metrics_lock:
                            latest_metrics["calibration_message"] = f"MAR calibrated: {new_threshold:.3f}"
                            latest_metrics["calibration_time"] = time.time()
                            current_metrics["calibration_message"] = latest_metrics["calibration_message"]
                            current_metrics["calibration_time"] = latest_metrics["calibration_time"]
                    except Exception as e:
                        print(f"[ERROR] Failed to set MAR threshold: {e}")
                else:
                    print("[WARNING] Cannot calibrate: No MAR value available (face not detected?)")
        elif key == ord('c') or key == ord('C'):  # 'c' for eyes closed calibration
            if engine and current_metrics.get("face_detected", False):
                current_ear = current_metrics.get("current_ear", 0.0)
                if current_ear > 0:
                    # Set threshold to slightly below current EAR (eyes closed)
                    new_threshold = max(0.05, current_ear * 0.9)  # 90% of closed EAR
                    try:
                        engine.set_ear_threshold(new_threshold)
                        print(f"[CALIBRATION] EAR threshold set to {new_threshold:.3f} (eyes closed: {current_ear:.3f})")
                        # Show confirmation on screen
                        with metrics_lock:
                            latest_metrics["calibration_message"] = f"EAR calibrated: {new_threshold:.3f}"
                            latest_metrics["calibration_time"] = time.time()
                    except Exception as e:
                        print(f"[ERROR] Failed to set EAR threshold: {e}")
                else:
                    print("[WARNING] Cannot calibrate: No EAR value available (face not detected?)")
        elif key == ord('y') or key == ord('Y'):  # 'y' for yawn calibration
            if engine and current_metrics.get("face_detected", False):
                current_mar = current_metrics.get("current_mar", 0.0)
                if current_mar > 0:
                    # Set threshold to slightly above current MAR (mouth open during yawn)
                    # For yawn, we want to detect when MAR exceeds this threshold
                    new_threshold = max(0.20, current_mar * 0.85)  # 85% of yawn MAR
                    try:
                        engine.set_mar_threshold(new_threshold)
                        print(f"[CALIBRATION] MAR threshold set to {new_threshold:.3f} (mouth open: {current_mar:.3f})")
                        # Show confirmation on screen
                        with metrics_lock:
                            latest_metrics["calibration_message"] = f"MAR calibrated: {new_threshold:.3f}"
                            latest_metrics["calibration_time"] = time.time()
                    except Exception as e:
                        print(f"[ERROR] Failed to set MAR threshold: {e}")
                else:
                    print("[WARNING] Cannot calibrate: No MAR value available (face not detected?)")
    
    try:
        cv2.destroyWindow(window_name)
    except:
        pass


def calculate_torso_roi(face_bbox: dict, frame_shape, scale_factor: float = 1.0) -> tuple:
    """Calculate torso ROI relative to face bounding box (matches C++ logic)."""
    if not face_bbox or face_bbox.get("width", 0) == 0:
        return None
    
    h, w = frame_shape[:2]
    # Scale up from downscaled coordinates to original frame
    face_x = int(face_bbox.get("x", 0) * scale_factor)
    face_y = int(face_bbox.get("y", 0) * scale_factor)
    face_w = int(face_bbox.get("width", 0) * scale_factor)
    face_h = int(face_bbox.get("height", 0) * scale_factor)
    
    # Torso extends below face: 1.5x face width, 2x face height down
    face_center_x = face_x + face_w // 2
    face_center_y = face_y + face_h // 2
    
    torso_width = int(face_w * 1.5)
    torso_height = int(face_h * 2.0)
    
    torso_x = face_center_x - torso_width // 2
    torso_y = face_center_y + face_h // 2  # Start below face
    
    # Clamp to image bounds
    torso_x = max(0, min(torso_x, w - torso_width))
    torso_y = max(0, min(torso_y, h - torso_height))
    torso_width = min(torso_width, w - torso_x)
    torso_height = min(torso_height, h - torso_y)
    
    if torso_width <= 0 or torso_height <= 0:
        return None
    
    return (torso_x, torso_y, torso_width, torso_height)


def scale_landmarks(landmarks: list, scale_factor: float) -> list:
    """Scale landmark coordinates from downscaled to original frame."""
    if not landmarks or scale_factor <= 0:
        return []
    return [coord * scale_factor for coord in landmarks]


def draw_metrics_overlay(frame, metrics: dict, engine=None):
    """Draw fatigue metrics as overlay on frame with detection regions."""
    global pvt_display_state, pvt_display_lock
    h, w = frame.shape[:2]
    
    # Draw detection regions FIRST (before text overlay)
    face_bbox = metrics.get("face_bbox", {})
    face_detected = face_bbox.get("width", 0) > 0
    scale_factor = metrics.get("scale_factor", 1.0)  # Scale from downscaled to original
    
    if face_detected:
        # MediaPipe coordinates are already in original frame (no scaling needed)
        # But keep scale_factor for compatibility with old code
        face_x = int(face_bbox.get("x", 0))
        face_y = int(face_bbox.get("y", 0))
        face_w = int(face_bbox.get("width", 0))
        face_h = int(face_bbox.get("height", 0))
        
        # Draw face bounding box (GREEN)
        cv2.rectangle(frame, (face_x, face_y), (face_x + face_w, face_y + face_h), 
                     (0, 255, 0), 2)
        cv2.putText(frame, "FACE", (face_x, face_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
        
        # Draw left eye landmarks (BLUE) - MediaPipe coordinates already scaled
        left_eye = metrics.get("left_eye_points", [])
        if len(left_eye) >= 12:  # 6 points * 2 (x,y)
            points = []
            for i in range(0, len(left_eye), 2):
                if i + 1 < len(left_eye):
                    x, y = int(left_eye[i]), int(left_eye[i + 1])
                    points.append((x, y))
                    cv2.circle(frame, (x, y), 4, (255, 0, 0), -1)  # Blue dots only, no lines
            if len(points) > 0:
                cv2.putText(frame, "LEFT EYE", (points[0][0] - 40, points[0][1] - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        else:
            cv2.putText(frame, "LEFT EYE: NOT FOUND", (face_x, face_y + 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Draw right eye landmarks (BLUE) - MediaPipe coordinates already scaled
        right_eye = metrics.get("right_eye_points", [])
        if len(right_eye) >= 12:
            points = []
            for i in range(0, len(right_eye), 2):
                if i + 1 < len(right_eye):
                    x, y = int(right_eye[i]), int(right_eye[i + 1])
                    points.append((x, y))
                    cv2.circle(frame, (x, y), 4, (255, 0, 0), -1)  # Blue dots only, no lines
            if len(points) > 0:
                cv2.putText(frame, "RIGHT EYE", (points[0][0] - 40, points[0][1] - 15),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
        else:
            cv2.putText(frame, "RIGHT EYE: NOT FOUND", (face_x, face_y + 50),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Draw mouth landmarks (YELLOW) - use MediaPipe landmarks
        mouth_points_list = metrics.get("mouth_points", [])
        if mouth_points_list and len(mouth_points_list) >= 4:  # At least 2 points (x,y pairs)
            points = []
            for i in range(0, len(mouth_points_list), 2):
                if i + 1 < len(mouth_points_list):
                    x, y = int(mouth_points_list[i]), int(mouth_points_list[i + 1])
                    points.append((x, y))
                    cv2.circle(frame, (x, y), 3, (0, 255, 255), -1)  # Yellow dots only, no lines
            
            if len(points) > 0:
                cv2.putText(frame, "MOUTH", (points[0][0], points[0][1] + 20),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        else:
            # No mouth points available
            cv2.putText(frame, "MOUTH: NOT FOUND", (face_x, face_y + 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Draw nose tip (YELLOW) - MediaPipe coordinates already scaled
        nose_tip = metrics.get("nose_tip", [])
        if len(nose_tip) >= 2:
            x, y = int(nose_tip[0]), int(nose_tip[1])
            cv2.circle(frame, (x, y), 5, (0, 255, 255), -1)  # Yellow circle
            cv2.putText(frame, "NOSE", (x + 15, y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
        else:
            cv2.putText(frame, "NOSE: NOT FOUND", (face_x, face_y + 90),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
        
        # Draw torso/shoulder ROI (ORANGE) - MediaPipe uses original frame, no scaling
        torso_roi = calculate_torso_roi(face_bbox, frame.shape, 1.0)
        if torso_roi:
            tx, ty, tw, th = torso_roi
            cv2.rectangle(frame, (tx, ty), (tx + tw, ty + th), 
                         (255, 165, 0), 2)  # Orange rectangle
            cv2.putText(frame, "TORSO/SHOULDER ROI", (tx, ty - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
        else:
            cv2.putText(frame, "TORSO ROI: CAN'T CALCULATE", (face_x, face_y + 110),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
    else:
        # No face detected - show message
        cv2.putText(frame, "NO FACE DETECTED", (w // 2 - 150, h // 2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, "Move closer / Face camera directly", (w // 2 - 200, h // 2 + 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Create semi-transparent overlay for text panel
    overlay = frame.copy()
    
    # Background panel for text (left side) - smaller
    panel_width = 280
    cv2.rectangle(overlay, (10, 10), (panel_width, h - 10), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    # Text properties - smaller, anti-aliased
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.5  # Slightly larger for better readability
    thickness = 1
    line_type = cv2.LINE_AA  # Anti-aliased lines for smoother text
    color_good = (0, 255, 0)  # Green
    color_warning = (0, 165, 255)  # Orange
    color_danger = (0, 0, 255)  # Red
    color_text = (255, 255, 255)  # White
    
    y_pos = 30
    line_height = 22
    
    # Title - smaller
    cv2.putText(frame, "FATIGUE DETECTION", (15, y_pos), font, 0.55, color_text, 1, line_type)
    y_pos += 28
    
    # Manual Offset Display - removed (not needed with MediaPipe)
    # y_pos += line_height
    
    # Face detection status
    face_detected = metrics.get("face_detected", False)
    face_status = "FACE: DETECTED" if face_detected else "FACE: NOT DETECTED"
    face_color = color_good if face_detected else color_danger
    cv2.putText(frame, face_status, (15, y_pos), font, font_scale, face_color, thickness, line_type)
    y_pos += line_height
    
    # Fatigue score (main metric)
    fatigue_score = metrics.get("fatigue_score", 0.0)
    fatigue_color = color_good if fatigue_score < 0.5 else (color_warning if fatigue_score < 0.7 else color_danger)
    cv2.putText(frame, f"FATIGUE: {fatigue_score:.2f}", (15, y_pos), 
               font, font_scale + 0.1, fatigue_color, thickness, line_type)
    y_pos += line_height
    
    # Fatigue level
    fatigue_level = metrics.get("fatigue_level", "unknown").upper()
    cv2.putText(frame, f"LEVEL: {fatigue_level}", (15, y_pos), font, font_scale, fatigue_color, thickness, line_type)
    y_pos += line_height + 5
    
    # Blink rate and counter
    blink_rate = metrics.get("blink_rate", 0.0)
    blink_count_total = metrics.get("blink_count_total", 0)
    cv2.putText(frame, f"Blink: {blink_rate:.1f}/min", (15, y_pos), 
               font, font_scale, color_text, thickness, line_type)
    y_pos += line_height
    cv2.putText(frame, f"Count: {blink_count_total}", (15, y_pos), 
               font, font_scale - 0.05, color_text, 1, line_type)
    y_pos += line_height - 5
    
    # PERCLOS (eye closure) - shows percentage of time eyes are closed
    perclos = metrics.get("perclos", 0.0)
    perclos_color = color_good if perclos < 0.2 else (color_warning if perclos < 0.5 else color_danger)
    cv2.putText(frame, f"Eye Closure: {perclos:.1%}", (15, y_pos), 
               font, font_scale, perclos_color, thickness, line_type)
    y_pos += line_height
    
    # EAR value (for calibration/debugging)
    current_ear = metrics.get("current_ear", 0.0)
    if current_ear > 0:  # Only show if available
        # Get current threshold from engine if available
        ear_threshold = 0.20  # Default fallback
        try:
            if engine:
                ear_threshold = engine.get_ear_threshold()
        except:
            pass
        ear_status = "OPEN" if current_ear > ear_threshold else "CLOSED"
        ear_color = color_good if current_ear > ear_threshold else color_warning
        cv2.putText(frame, f"EAR: {current_ear:.3f} ({ear_status}) [Th: {ear_threshold:.2f}]", (15, y_pos), 
                   font, font_scale - 0.1, ear_color, 1, line_type)
        y_pos += line_height
    
    # MAR value (for calibration/debugging)
    current_mar = metrics.get("current_mar", 0.0)
    if current_mar > 0:  # Only show if available
        # Get current threshold from engine if available
        mar_threshold = 0.8  # Default fallback
        try:
            if engine:
                mar_threshold = engine.get_mar_threshold()
        except:
            pass
        mar_status = "OPEN" if current_mar > mar_threshold else "CLOSED"
        mar_color = color_warning if current_mar > mar_threshold else color_text
        cv2.putText(frame, f"MAR: {current_mar:.3f} ({mar_status}) [Th: {mar_threshold:.2f}]", (15, y_pos), 
                   font, font_scale - 0.1, mar_color, 1, line_type)
        y_pos += line_height
    
    # Calibration message (show for 3 seconds after calibration)
    calibration_msg = metrics.get("calibration_message", "")
    calibration_time = metrics.get("calibration_time", 0)
    if calibration_msg and (time.time() - calibration_time) < 3.0:  # Show for 3 seconds
        cv2.putText(frame, f"✓ {calibration_msg}", (15, y_pos), 
                   font, font_scale, color_good, 2, line_type)
        y_pos += line_height + 10
    
    # Yawn count
    yawn_count = metrics.get("yawn_count_5min", metrics.get("yawn_count", 0))
    cv2.putText(frame, f"Yawns (5min): {yawn_count}", (15, y_pos), 
               font, font_scale, color_text, thickness, line_type)
    y_pos += line_height
    
    # Gaze stability with state detection
    gaze_stability = metrics.get("gaze_stability", 0.0)
    blink_rate = metrics.get("blink_rate", 0.0)
    gaze_color = color_good if gaze_stability > 0.7 else (color_warning if gaze_stability > 0.4 else color_danger)
    cv2.putText(frame, f"Gaze Stability: {gaze_stability:.2f}", (15, y_pos), 
               font, font_scale, gaze_color, thickness, line_type)
    y_pos += line_height
    
    # DEBUG: Zoning Out vs Locking In Detection
    if face_detected:
        # Get head pose angles
        head_pitch = metrics.get("head_pitch", 0.0)
        head_yaw = metrics.get("head_yaw", 0.0)
        head_roll = metrics.get("head_roll", 0.0)
        
        # Get gaze direction from vision data
        gaze_x = metrics.get("gaze_x", 0.0)  # Normalized eye position (-0.5 to 0.5)
        gaze_y = metrics.get("gaze_y", 0.0)
        
        # Track head position history for stillness detection
        head_position_history.append((head_pitch, head_yaw, head_roll))
        if len(head_position_history) > max_head_history:
            head_position_history.pop(0)
        
        # Track gaze position history for reading vs zoning detection
        gaze_position_history.append((gaze_x, gaze_y))
        if len(gaze_position_history) > max_gaze_history:
            gaze_position_history.pop(0)
        
        # Calculate head movement variance (how much head is changing frame-to-frame)
        if len(head_position_history) > 5:
            pitches = [h[0] for h in head_position_history]
            yaws = [h[1] for h in head_position_history]
            rolls = [h[2] for h in head_position_history]
            
            pitch_var = np.var(pitches)
            yaw_var = np.var(yaws)
            roll_var = np.var(rolls)
            head_movement_variance = pitch_var + yaw_var + roll_var
        else:
            head_movement_variance = 0.0
        
        # Calculate gaze movement variance (how much eyes are moving around)
        if len(gaze_position_history) > 5:
            gaze_xs = [g[0] for g in gaze_position_history]
            gaze_ys = [g[1] for g in gaze_position_history]
            
            gaze_x_var = np.var(gaze_xs)
            gaze_y_var = np.var(gaze_ys)
            gaze_movement_variance = gaze_x_var + gaze_y_var
        else:
            gaze_movement_variance = 0.0
        
        # Show current values for debugging
        cv2.putText(frame, f"[Stab: {gaze_stability:.2f}, HeadVar: {head_movement_variance:.2f}, GazeVar: {gaze_movement_variance:.4f}]", (15, y_pos), 
                   font, font_scale - 0.1, (200, 200, 200), 1, line_type)
        y_pos += line_height - 5
        
        # DETECTION LOGIC:
        # ZONING OUT: Gaze stable + Head still + Eyes not moving around
        # LOCKING IN: Gaze unstable (saccades) + Eyes moving around (reading/scanning)
        
        if gaze_stability > 0.531 and head_movement_variance < 1.0 and gaze_movement_variance < 0.0005:
            # All three conditions: stable gaze, still head, eyes locked on one point
            cv2.putText(frame, ">>> ZONING OUT <<<", (15, y_pos), 
                       font, font_scale + 0.15, (0, 0, 255), 2, line_type)  # RED
            y_pos += line_height + 5
            cv2.putText(frame, "(Thousand-yard stare)", (15, y_pos), 
                       font, font_scale - 0.05, (0, 100, 255), 1, line_type)
        elif gaze_stability < 0.434 or gaze_movement_variance > 0.001:
            # Either low gaze stability (saccades) OR eyes moving around
            cv2.putText(frame, ">>> LOCKING IN <<<", (15, y_pos), 
                       font, font_scale + 0.15, (0, 255, 0), 2, line_type)  # GREEN
            y_pos += line_height + 5
            cv2.putText(frame, "(Reading/scanning)", (15, y_pos), 
                       font, font_scale - 0.05, (100, 255, 100), 1, line_type)
        else:
            cv2.putText(frame, "Transition state", (15, y_pos), 
                       font, font_scale - 0.05, (150, 150, 150), 1, line_type)
        y_pos += line_height
    
    # Debug: Show raw MAR for yawn detection
    mar_raw = metrics.get("mar_raw", metrics.get("current_mar", 0.0))
    cv2.putText(frame, f"MAR: {mar_raw:.3f} (threshold: 0.20)", (15, y_pos), 
               font, font_scale - 0.05, color_text, 1, line_type)
    y_pos += line_height - 5
    
    # Gaze direction (for testing - move head left/right/up/down to see values change)
    gaze_x = metrics.get("gaze_x", 0.0)
    gaze_y = metrics.get("gaze_y", 0.0)
    cv2.putText(frame, f"Gaze: X={gaze_x:.3f}, Y={gaze_y:.3f}", (15, y_pos), 
               font, font_scale - 0.05, (0, 255, 255), 2, line_type)
    y_pos += line_height - 5
    # Show calibration status
    if vision_system:
        cal = vision_system.get_gaze_calibration()
        if cal["calibrated"]:
            cv2.putText(frame, f"Gaze CALIBRATED: X[{cal['gaze_x_min']:.2f}, {cal['gaze_x_max']:.2f}] Y[{cal['gaze_y_min']:.2f}, {cal['gaze_y_max']:.2f}]", (15, y_pos), 
                       font, font_scale - 0.05, (0, 255, 0), 1, line_type)
            y_pos += line_height - 5
            cv2.putText(frame, f"Press 0 to reset calibration", (15, y_pos), 
                       font, font_scale - 0.05, (200, 200, 200), 1, line_type)
        else:
            cv2.putText(frame, f"Press 1/2/3/4 to calibrate (L/R/U/D)", (15, y_pos), 
                       font, font_scale - 0.05, (255, 255, 0), 1, line_type)
        y_pos += line_height - 5
    
    # Head pose angles
    head_pitch = metrics.get("head_pitch", 0.0)
    head_yaw = metrics.get("head_yaw", 0.0)
    head_roll = metrics.get("head_roll", 0.0)
    cv2.putText(frame, f"Head: P={head_pitch:.1f}deg, Y={head_yaw:.1f}deg, R={head_roll:.1f}deg", (15, y_pos), 
               font, font_scale - 0.05, (255, 255, 0), 2, line_type)
    y_pos += line_height - 5
    
    # Fidget score
    fidget_score = metrics.get("fidgeting_score", metrics.get("fidget_score", 0.0))
    cv2.putText(frame, f"Fidget Score: {fidget_score:.2f}", (15, y_pos), 
               font, font_scale, color_text, thickness, line_type)
    y_pos += line_height
    
    # Neck cracks
    neck_cracks = metrics.get("neck_crack_count_1min", 0)
    if neck_cracks > 0:
        cv2.putText(frame, f"Neck Cracks: {neck_cracks}", (15, y_pos), 
                   font, font_scale, color_warning, thickness, line_type)
        y_pos += line_height
    
    # PVT Challenge indicator (if active)
    with pvt_display_lock:
        pvt_active = pvt_display_state.get("active", False)
        pvt_msg = pvt_display_state.get("message", "")
    
    if pvt_active and pvt_msg:
        y_pos += 10
        # Highlighted background for PVT challenge
        pvt_bg_y = y_pos - 25
        pvt_bg_height = 45
        overlay_pvt = frame.copy()
        cv2.rectangle(overlay_pvt, (15, pvt_bg_y), (panel_width - 5, pvt_bg_y + pvt_bg_height), (0, 100, 255), -1)
        cv2.addWeighted(overlay_pvt, 0.6, frame, 0.4, 0, frame)
        
        # PVT Challenge text (large and prominent)
        if "PRESS SPACEBAR NOW" in pvt_msg.upper():
            cv2.putText(frame, "*** PVT CHALLENGE ***", (15, y_pos), 
                       font, font_scale + 0.3, (0, 255, 255), 3, line_type)
            y_pos += line_height + 5
            cv2.putText(frame, "PRESS SPACEBAR NOW!", (15, y_pos), 
                       font, font_scale + 0.4, (0, 255, 0), 3, line_type)
        else:
            cv2.putText(frame, "PVT Challenge:", (15, y_pos), 
                       font, font_scale + 0.1, (0, 165, 255), 2, line_type)
            y_pos += line_height
            cv2.putText(frame, pvt_msg, (15, y_pos), 
                       font, font_scale, (0, 255, 255), 2, line_type)
        y_pos += line_height + 10
    
    # Recommendation
    recommendation = metrics.get("recommendation", "continue")
    rec_text = recommendation.replace("_", " ").upper()
    rec_color = color_good if "continue" in recommendation else color_warning
    y_pos += 10
    cv2.putText(frame, f"REC: {rec_text}", (15, y_pos),
               font, font_scale, rec_color, thickness, line_type)
    y_pos += line_height + 10
    
    # Calibration instructions at bottom
    cv2.putText(frame, "CALIBRATION:", (20, h - 50), 
               font, font_scale - 0.1, color_text, 1)
    cv2.putText(frame, "Press 'C' when eyes CLOSED", (20, h - 30), 
               font, font_scale - 0.2, (0, 255, 255), 1)
    cv2.putText(frame, "Press 'Y' when YAWNING", (20, h - 10), 
               font, font_scale - 0.2, (0, 255, 255), 1)
    
    return frame


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown (replaces deprecated on_event)."""
    global show_camera_window
    
    # Startup
    try:
        initialize_camera()
        
        # Start camera display thread
        if show_camera_window:
            display_thread = threading.Thread(target=display_camera_loop, daemon=True)
            display_thread.start()
            print("[INFO] Camera display window started in background thread")
        
    except Exception as e:
        print(f"[ERROR] Failed to initialize on startup: {e}")
        print("[INFO] Server will start, but camera won't be available until /api/fatigue/set-user is called")
    
    yield  # App runs here
    
    # Shutdown
    global camera, engine
    show_camera_window = False
    if camera:
        camera.release()
        print("[INFO] Camera released")
    engine = None
    cv2.destroyAllWindows()


app = FastAPI(
    title="Fatigue Detection Daemon",
    lifespan=lifespan
)

# CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


def sanitize_for_json(obj):
    """Convert numpy/C++ types to native Python types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.bool_, bool)):
        return bool(obj)
    elif isinstance(obj, (np.integer, int)):
        return int(obj)
    elif isinstance(obj, (np.floating, float)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    else:
        return obj


@app.websocket("/ws/fatigue-detect")
async def fatigue_websocket(websocket: WebSocket):
    """WebSocket endpoint that streams fatigue metrics (JSON only)."""
    # Accept all origins for WebSocket (CORS doesn't apply to WS, but we need to accept)
    await websocket.accept()
    active_connections.add(websocket)
    
    print(f"[INFO] New WebSocket connection. Total connections: {len(active_connections)}")
    
    # Initialize PVT challenge for this connection
    pvt_challenge = PVTChallenge()
    with pvt_lock:
        pvt_challenges[websocket] = pvt_challenge
    
    # Initialize notification manager
    notification_manager = get_notification_manager()
    last_recommendation: Optional[str] = None
    
    # Send a test notification on connection to verify notifications work
    print("[INFO] Sending test notification to verify system...")
    notification_manager._show_notification(
        "Lock In Labs",
        "Fatigue detection connected. Notifications are active!",
        duration=3
    )
    
    last_pvt_time = 0
    pvt_cooldown_ms = 10000  # 10 seconds between PVT challenges
    pvt_pending_response = False  # Track if we're waiting for a PVT response
    
    # Create tasks for receiving messages and sending metrics
    async def receive_messages():
        """Handle incoming WebSocket messages (PVT responses, etc.)"""
        nonlocal pvt_pending_response
        try:
            while True:
                try:
                    # Wait for message with timeout
                    data = await asyncio.wait_for(websocket.receive_json(), timeout=1.0)
                    
                    # Handle PVT response
                    if data.get("type") == "pvt_response":
                        reaction_time_ms = data.get("reaction_time_ms")
                        if reaction_time_ms is not None and pvt_challenge.is_active:
                            # Record response (frontend sends the reaction time)
                            pvt_challenge.record_response(reaction_time_ms)
                            interpretation = pvt_challenge.interpret_response()
                            
                            # Send interpretation back to client
                            await websocket.send_json({
                                "type": "pvt_result",
                                "reaction_time_ms": reaction_time_ms,
                                "interpretation": interpretation.get("interpretation"),
                                "status": interpretation.get("status"),
                                "message": interpretation.get("message", "")
                            })
                            
                            # Handle interpretation
                            if interpretation.get("interpretation") == "alert":
                                # False alarm - reset fatigue score (if possible)
                                # Note: We can't directly modify C++ engine score,
                                # but we can mark this in metrics for frontend to handle
                                print(f"[PVT] Alert response (<250ms) - camera was wrong, fatigue reset recommended")
                            elif interpretation.get("interpretation") in ["impaired", "severely_impaired"]:
                                print(f"[PVT] Impaired response ({reaction_time_ms}ms) - fatigue confirmed")
                            
                            pvt_challenge.reset()
                            pvt_pending_response = False
                            
                            # Clear PVT display state
                            with pvt_display_lock:
                                pvt_display_state["active"] = False
                                pvt_display_state["message"] = ""
                except asyncio.TimeoutError:
                    # No message received, continue
                    continue
                except WebSocketDisconnect:
                    break
        except Exception as e:
            print(f"[ERROR] Error in receive_messages: {e}")
    
    # Start receiving messages in background
    receive_task = asyncio.create_task(receive_messages())
    
    try:
        while True:
            if camera is None or engine is None:
                await websocket.send_json({
                    "type": "error",
                    "message": "Camera or engine not initialized. Call /api/fatigue/set-user/{user_id} first."
                })
                await asyncio.sleep(1)
                continue
            
            # 1. Capture frame locally (Fast, no encoding)
            ret, frame = camera.read()
            if not ret:
                await websocket.send_json({
                    "type": "error",
                    "message": "Failed to capture frame"
                })
                break
            
            # 2. Process frame with C++ (Zero-copy numpy array)
            # OpenCV Mat is already in BGR format (uint8)
            # Ensure frame is contiguous
            if not frame.flags['C_CONTIGUOUS']:
                frame = frame.copy()
            
            timestamp_ms = int(time.time() * 1000)
            try:
                # Process frame with MediaPipe vision system
                vision_results = vision_system.process(frame)
                
                # ====================================================================
                # THREE-GATE SYSTEM: Calculate context and focus multipliers
                # ====================================================================
                # Gate 1: Context (active window) - Poll every 2s (cached internally)
                active_window_title = "Unknown"
                context_multiplier = 0.5  # Default: neutral
                if window_tracker:
                    try:
                        active_window_title, context_multiplier = window_tracker.get_active_window()
                    except Exception as e:
                        print(f"[ERROR] WindowTracker failed: {e}")
                
                # Gate 2: Focus (screen attention) - Check every frame
                looking_at_screen = False
                focus_multiplier = 0.0
                phone_detected = False  # TODO: Connect to phone detector WebSocket
                if screen_geometry and vision_results and vision_results.get("face_detected"):
                    gaze_x = vision_results.get("gaze_x", 0.0)
                    gaze_y = vision_results.get("gaze_y", 0.0)
                    looking_at_screen = screen_geometry.is_looking_at_screen(gaze_x, gaze_y)
                    focus_multiplier = screen_geometry.get_focus_multiplier(gaze_x, gaze_y, phone_detected)
                # ====================================================================
                
                if vision_results and vision_results.get("face_detected"):
                    # Update C++ engine with MediaPipe metrics
                    metrics = engine.update_metrics(
                        ear=vision_results["ear"],
                        mar=vision_results["mar"],
                        gaze_x=vision_results["gaze_x"],
                        gaze_y=vision_results["gaze_y"],
                        timestamp_ms=timestamp_ms,
                        face_detected=True,
                        head_pitch=vision_results.get("head_pitch", 0.0),
                        head_yaw=vision_results.get("head_yaw", 0.0),
                        head_roll=vision_results.get("head_roll", 0.0)
                    )
                    
                    # Inject gate multipliers into metrics (C++ calculated lock_in_score)
                    # C++ computes: lock_in_score = context × focus × (1 - fatigue)
                    # We need to pass these to C++ via StateVector
                    # For now, add to Python metrics dict (C++ integration pending)
                    metrics["active_window"] = active_window_title
                    metrics["context_multiplier"] = context_multiplier
                    metrics["looking_at_screen"] = looking_at_screen
                    metrics["phone_detected"] = phone_detected
                    metrics["focus_multiplier"] = focus_multiplier
                    
                    # Calculate lock_in_score in Python (until C++ integration complete)
                    fatigue_score = metrics.get("fatigue_score", 0.0)
                    fatigue_multiplier = 1.0 - fatigue_score
                    lock_in_score = context_multiplier * focus_multiplier * fatigue_multiplier
                    metrics["fatigue_multiplier"] = fatigue_multiplier
                    metrics["lock_in_score"] = lock_in_score
                    # Add MediaPipe face bbox to metrics for display
                    if vision_results.get("face_bbox"):
                        x, y, w, h = vision_results["face_bbox"]
                        metrics["face_bbox"] = {"x": x, "y": y, "width": w, "height": h}
                        metrics["face_detected"] = True
                        metrics["scale_factor"] = 1.0  # MediaPipe uses original frame, no scaling
                    
                    # Extract MediaPipe landmarks for display
                    if vision_results.get("landmarks"):
                        landmarks = vision_results["landmarks"]
                        h_frame, w_frame = frame.shape[:2]
                        
                        # Left eye (simplified - use 6 key points)
                        left_eye_indices = [33, 133, 157, 158, 159, 160]
                        left_eye_points = []
                        for idx in left_eye_indices:
                            if idx < len(landmarks):
                                pt = landmarks[idx]
                                left_eye_points.extend([pt.x * w_frame, pt.y * h_frame])
                        
                        # Right eye (simplified)
                        right_eye_indices = [362, 263, 387, 388, 389, 390]
                        right_eye_points = []
                        for idx in right_eye_indices:
                            if idx < len(landmarks):
                                pt = landmarks[idx]
                                right_eye_points.extend([pt.x * w_frame, pt.y * h_frame])
                        
                        # Mouth (use key points)
                        mouth_indices = [61, 291, 39, 181, 0, 17, 269, 405, 13, 14]
                        mouth_points = []
                        for idx in mouth_indices:
                            if idx < len(landmarks):
                                pt = landmarks[idx]
                                mouth_points.extend([pt.x * w_frame, pt.y * h_frame])
                        
                        # Nose tip
                        nose_tip = []
                        if 1 < len(landmarks):
                            pt = landmarks[1]
                            nose_tip = [pt.x * w_frame, pt.y * h_frame]
                        
                        metrics["left_eye_points"] = left_eye_points
                        metrics["right_eye_points"] = right_eye_points
                        metrics["mouth_points"] = mouth_points
                        metrics["nose_tip"] = nose_tip
                        
                        # Add gaze and head pose angles for display
                        metrics["gaze_x"] = vision_results.get("gaze_x", 0.0)
                        metrics["gaze_y"] = vision_results.get("gaze_y", 0.0)
                        metrics["head_pitch"] = vision_results.get("head_pitch", 0.0)
                        metrics["head_yaw"] = vision_results.get("head_yaw", 0.0)
                        metrics["head_roll"] = vision_results.get("head_roll", 0.0)
                        metrics["mar_raw"] = vision_results.get("mar", 0.0)  # Debug: show raw MAR
                else:
                    # No face detected - zero out all gate multipliers
                    metrics = engine.update_metrics(
                        ear=0.0,
                        mar=0.0,
                        gaze_x=0.0,
                        gaze_y=0.0,
                        timestamp_ms=timestamp_ms,
                        face_detected=False
                    )
                    metrics["face_detected"] = False
                    metrics["face_bbox"] = {"x": 0, "y": 0, "width": 0, "height": 0}
                    
                    # Set gate multipliers to 0 (no face = no productivity)
                    metrics["active_window"] = active_window_title  # Still track window
                    metrics["context_multiplier"] = context_multiplier  # Keep context value
                    metrics["looking_at_screen"] = False
                    metrics["phone_detected"] = False
                    metrics["focus_multiplier"] = 0.0  # No face = no focus
                    metrics["fatigue_multiplier"] = 0.0
                    metrics["lock_in_score"] = 0.0
                
                # Update latest metrics for display thread
                with metrics_lock:
                    latest_metrics = metrics
            except Exception as e:
                print(f"[ERROR] Failed to process frame: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Processing error: {str(e)}"
                })
                await asyncio.sleep(0.033)
                continue
            
            # 3. Send ONLY lightweight JSON metrics (no images!)
            # Sanitize metrics to ensure all types are JSON-serializable
            try:
                sanitized_metrics = sanitize_for_json(metrics)
                await websocket.send_json({
                    "type": "metrics",
                    "timestamp": timestamp_ms,
                    "data": sanitized_metrics
                })
            except Exception as e:
                print(f"[ERROR] Failed to send metrics: {e}")
                await websocket.send_json({
                    "type": "error",
                    "message": f"Serialization error: {str(e)}"
                })
                await asyncio.sleep(0.033)
                continue
            
            # 3.5. Check for notifications (not locked in, fatigue, break needed)
            # Only check if face is detected (valid metrics)
            face_detected = metrics.get("face_detected", False)
            if face_detected:
                # Debug: Log metrics occasionally
                import random
                if random.random() < 0.01:  # 1% of the time
                    fatigue_score = metrics.get("fatigue_score", 0.0)
                    z_scores = {
                        "blink": metrics.get("z_score_blink", 0.0),
                        "gaze": metrics.get("z_score_gaze", 0.0),
                        "fidget": metrics.get("z_score_fidget", 0.0),
                        "posture": metrics.get("z_score_posture", 0.0),
                    }
                    recommendation = metrics.get("recommendation", "continue")
                    print(f"[DEBUG] Metrics - fatigue: {fatigue_score:.2f}, Z-scores: {z_scores}, rec: {recommendation}")
                
                # Check for "not locked in" (distraction) - based on Z-scores
                notification_manager.check_not_locked_in(metrics)
                
                # Check for fatigue
                notification_manager.check_fatigue(metrics)
                
                # Check for break needed (when recommendation changes)
                current_recommendation = metrics.get("recommendation", "continue")
                notification_manager.check_break_needed(metrics, last_recommendation)
                last_recommendation = current_recommendation
            else:
                # Debug: Log when face not detected
                import random
                if random.random() < 0.01:  # 1% of the time
                    print("[DEBUG] Face not detected - notifications skipped")
            
            # 4. Check for PVT challenge trigger (only if not already pending)
            fatigue_score = metrics.get("fatigue_score", 0.0)
            current_time_ms = timestamp_ms
            
            if (fatigue_score >= 0.7 and 
                not pvt_pending_response and
                not pvt_challenge.is_active and
                (current_time_ms - last_pvt_time) > pvt_cooldown_ms):
                
                delay_ms = random.randint(1000, 5000)
                pvt_challenge.trigger(delay_ms=delay_ms)
                pvt_pending_response = True
                
                # Update shared PVT display state for camera overlay
                with pvt_display_lock:
                    pvt_display_state["active"] = True
                    pvt_display_state["message"] = "PVT Challenge starting..."
                    pvt_display_state["trigger_time"] = current_time_ms
                    pvt_display_state["delay_ms"] = delay_ms
                
                await websocket.send_json({
                    "type": "pvt_challenge",
                    "delay_ms": delay_ms,
                    "triggered_by_fatigue_score": fatigue_score,
                    "message": "Reaction test: Press SPACEBAR when shape appears"
                })
                last_pvt_time = current_time_ms
                print(f"[PVT] Challenge triggered (fatigue_score={fatigue_score:.2f}, delay={delay_ms}ms)")
                
                # Schedule message update after delay (when shape should appear)
                async def update_pvt_message():
                    await asyncio.sleep(delay_ms / 1000.0)
                    with pvt_display_lock:
                        if pvt_display_state["active"]:
                            pvt_display_state["message"] = "PRESS SPACEBAR NOW!"
                
                asyncio.create_task(update_pvt_message())
            
            # 5. Non-blocking sleep to target ~30 FPS (33ms per frame)
            await asyncio.sleep(0.033)
            
    except WebSocketDisconnect:
        print("[INFO] WebSocket disconnected")
    except Exception as e:
        print(f"[ERROR] WebSocket error: {e}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
        except:
            pass
    finally:
        receive_task.cancel()
        try:
            await receive_task
        except asyncio.CancelledError:
            pass
        active_connections.discard(websocket)
        with pvt_lock:
            pvt_challenges.pop(websocket, None)
        # Clear PVT display state if no more connections
        if len(active_connections) == 0:
            with pvt_display_lock:
                pvt_display_state["active"] = False
                pvt_display_state["message"] = ""
        print(f"[INFO] WebSocket connection closed. Total connections: {len(active_connections)}")


@app.post("/api/fatigue/set-user/{user_id}")
async def set_user(user_id: str, camera_index: int = 0):
    """Switch to different user profile or initialize if not already done."""
    global camera, engine
    
    try:
        # Release old camera if exists
        if camera:
            camera.release()
        
        # Initialize new camera and engine
        initialize_camera(user_id, camera_index)
        
        return {
            "status": "ok",
            "user_id": user_id,
            "message": f"Initialized camera and engine for user: {user_id}"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e)
        }


@app.get("/api/fatigue/status")
async def get_status():
    """Get current status of the fatigue detection system."""
    return {
        "camera_initialized": camera is not None and camera.isOpened() if camera else False,
        "engine_initialized": engine is not None,
        "active_connections": len(active_connections)
    }


@app.post("/api/fatigue/pvt-response")
async def pvt_response(reaction_time_ms: int, user_id: Optional[str] = None):
    """
    Handle PVT challenge response from frontend (HTTP endpoint).
    Note: Prefer using WebSocket for real-time responses.
    """
    if reaction_time_ms < 0:
        return {"status": "error", "message": "Invalid reaction time"}
    
    # Interpret reaction time
    interpretation = interpret_reaction_time(reaction_time_ms)
    
    return {
        "status": "ok",
        "interpretation": interpretation,
        "reaction_time_ms": reaction_time_ms,
        "message": "For real-time responses, use WebSocket /ws/fatigue-detect endpoint"
    }


if __name__ == "__main__":
    import uvicorn
    import socket
    
    # Get port from environment or default to 8000
    port = int(os.environ.get("FATIGUE_PORT", "8000"))
    host = os.environ.get("FATIGUE_HOST", "127.0.0.1")
    
    # Check if port is available
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError as e:
        if e.errno == 10048:  # Windows: port already in use
            print(f"[ERROR] Port {port} is already in use!")
            print(f"[INFO] Kill the process using: netstat -ano | findstr :{port}")
            print(f"[INFO] Or use a different port: set FATIGUE_PORT=8001 && python app.py")
            sys.exit(1)
        else:
            raise
    
    print(f"[INFO] Starting fatigue detection daemon on http://{host}:{port}")
    print("[INFO] Camera will be opened on startup")
    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except OSError as e:
        if e.errno == 10048:
            print(f"[ERROR] Port {port} became unavailable. Another process may have claimed it.")
        raise
