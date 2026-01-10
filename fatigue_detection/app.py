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
from typing import Optional

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

# Global: Python owns the camera
camera: Optional[cv2.VideoCapture] = None
engine: Optional[FatigueEngine] = None
active_connections: set = set()  # Track active WebSocket connections
show_camera_window: bool = True  # Toggle camera display window
latest_metrics: Optional[dict] = None  # Latest metrics for display
metrics_lock = threading.Lock()  # Thread-safe access to metrics


def initialize_camera(user_id: str = "default_user", camera_index: int = 0):
    """Initialize camera and engine."""
    global camera, engine
    
    print(f"[INFO] Initializing camera and engine for user: {user_id}")
    
    # Open camera
    camera = cv2.VideoCapture(camera_index)
    if not camera.isOpened():
        raise RuntimeError(f"Failed to open camera {camera_index}")
    
    # Set camera properties (optional, for performance)
    camera.set(cv2.CAP_PROP_BUFFERSIZE, 1)  # Reduce latency
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # Or your preferred resolution
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    # Get actual camera resolution (might be different from requested)
    actual_width = int(camera.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"[INFO] Camera opened: {actual_width}x{actual_height}")
    
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
    global camera, engine, show_camera_window, latest_metrics
    
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
                    metrics = engine.process_frame(frame, timestamp_ms)
                    current_metrics = metrics
                    
                    # Update latest metrics (thread-safe)
                    with metrics_lock:
                        latest_metrics = metrics
                except Exception as e:
                    print(f"[ERROR] Display loop processing error: {e}")
                    # Create dummy metrics on error
                    current_metrics = {"face_detected": False, "fatigue_score": 0.0}
            
            frame_skip += 1
            
            # Draw metrics overlay on frame
            try:
                frame_with_overlay = draw_metrics_overlay(frame.copy(), current_metrics)
                
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
        if key == ord('q') or key == 27:  # 'q' or ESC
            print("[INFO] Camera window closed by user (press 'q' or ESC)")
            show_camera_window = False
            break
    
    try:
        cv2.destroyWindow(window_name)
    except:
        pass


def calculate_torso_roi(face_bbox: dict, frame_shape) -> tuple:
    """Calculate torso ROI relative to face bounding box (matches C++ logic)."""
    if not face_bbox or face_bbox.get("width", 0) == 0:
        return None
    
    h, w = frame_shape[:2]
    face_x = face_bbox.get("x", 0)
    face_y = face_bbox.get("y", 0)
    face_w = face_bbox.get("width", 0)
    face_h = face_bbox.get("height", 0)
    
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


def draw_metrics_overlay(frame, metrics: dict):
    """Draw fatigue metrics as overlay on frame with detection regions."""
    h, w = frame.shape[:2]
    
    # Draw detection regions FIRST (before text overlay)
    face_bbox = metrics.get("face_bbox", {})
    face_detected = face_bbox.get("width", 0) > 0
    
    if face_detected:
        # Draw face bounding box
        face_x = face_bbox.get("x", 0)
        face_y = face_bbox.get("y", 0)
        face_w = face_bbox.get("width", 0)
        face_h = face_bbox.get("height", 0)
        
        # Scale up from downscaled frame to original frame
        # Note: landmarks are on downscaled frame, but we're displaying original
        # For now, assume they're already scaled (we'll fix this if needed)
        
        cv2.rectangle(frame, (face_x, face_y), (face_x + face_w, face_y + face_h), 
                     (0, 255, 0), 2)  # Green box for face
        cv2.putText(frame, "FACE", (face_x, face_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        
        # Draw left eye landmarks
        left_eye = metrics.get("left_eye_points", [])
        if len(left_eye) >= 12:  # 6 points * 2 (x,y)
            for i in range(0, len(left_eye), 2):
                if i + 1 < len(left_eye):
                    x, y = int(left_eye[i]), int(left_eye[i + 1])
                    cv2.circle(frame, (x, y), 3, (255, 0, 0), -1)  # Blue for eyes
            # Draw eye outline
            if len(left_eye) >= 12:
                points = [(int(left_eye[i]), int(left_eye[i+1])) for i in range(0, 12, 2)]
                for i in range(len(points)):
                    cv2.line(frame, points[i], points[(i+1) % len(points)], (255, 0, 0), 1)
            cv2.putText(frame, "LEFT EYE", (int(left_eye[0]) - 30, int(left_eye[1]) - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
        
        # Draw right eye landmarks
        right_eye = metrics.get("right_eye_points", [])
        if len(right_eye) >= 12:
            for i in range(0, len(right_eye), 2):
                if i + 1 < len(right_eye):
                    x, y = int(right_eye[i]), int(right_eye[i + 1])
                    cv2.circle(frame, (x, y), 3, (255, 0, 0), -1)  # Blue for eyes
            # Draw eye outline
            if len(right_eye) >= 12:
                points = [(int(right_eye[i]), int(right_eye[i+1])) for i in range(0, 12, 2)]
                for i in range(len(points)):
                    cv2.line(frame, points[i], points[(i+1) % len(points)], (255, 0, 0), 1)
            cv2.putText(frame, "RIGHT EYE", (int(right_eye[0]) - 30, int(right_eye[1]) - 15),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (255, 0, 0), 1)
        
        # Draw mouth landmarks
        mouth = metrics.get("mouth_points", [])
        if len(mouth) >= 16:  # At least 8 points
            for i in range(0, min(16, len(mouth)), 2):
                if i + 1 < len(mouth):
                    x, y = int(mouth[i]), int(mouth[i + 1])
                    cv2.circle(frame, (x, y), 2, (0, 255, 255), -1)  # Yellow for mouth
        
        # Draw nose tip
        nose_tip = metrics.get("nose_tip", [])
        if len(nose_tip) >= 2:
            x, y = int(nose_tip[0]), int(nose_tip[1])
            cv2.circle(frame, (x, y), 4, (0, 255, 255), -1)  # Yellow for nose
            cv2.putText(frame, "NOSE", (x + 10, y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 255), 1)
        
        # Draw torso/shoulder ROI
        torso_roi = calculate_torso_roi(face_bbox, frame.shape)
        if torso_roi:
            tx, ty, tw, th = torso_roi
            cv2.rectangle(frame, (tx, ty), (tx + tw, ty + th), 
                         (255, 165, 0), 2)  # Orange for torso
            cv2.putText(frame, "TORSO/SHOULDER", (tx, ty - 10), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 165, 0), 1)
    else:
        # No face detected - show message
        cv2.putText(frame, "NO FACE DETECTED", (w // 2 - 150, h // 2), 
                   cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
        cv2.putText(frame, "Move closer / Face camera directly", (w // 2 - 200, h // 2 + 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
    
    # Create semi-transparent overlay for text panel
    overlay = frame.copy()
    
    # Background panel for text (left side)
    panel_width = 350
    cv2.rectangle(overlay, (10, 10), (panel_width, h - 10), (0, 0, 0), -1)
    cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
    
    # Text properties
    font = cv2.FONT_HERSHEY_SIMPLEX
    font_scale = 0.6
    thickness = 2
    color_good = (0, 255, 0)  # Green
    color_warning = (0, 165, 255)  # Orange
    color_danger = (0, 0, 255)  # Red
    color_text = (255, 255, 255)  # White
    
    y_pos = 40
    line_height = 35
    
    # Title
    cv2.putText(frame, "FATIGUE DETECTION", (20, y_pos), font, 0.8, color_text, 2)
    y_pos += 40
    
    # Face detection status
    face_detected = metrics.get("face_detected", False)
    face_status = "FACE: DETECTED" if face_detected else "FACE: NOT DETECTED"
    face_color = color_good if face_detected else color_danger
    cv2.putText(frame, face_status, (20, y_pos), font, font_scale, face_color, thickness)
    y_pos += line_height
    
    # Fatigue score (main metric)
    fatigue_score = metrics.get("fatigue_score", 0.0)
    fatigue_color = color_good if fatigue_score < 0.5 else (color_warning if fatigue_score < 0.7 else color_danger)
    cv2.putText(frame, f"FATIGUE: {fatigue_score:.2f}", (20, y_pos), 
               font, font_scale + 0.2, fatigue_color, thickness)
    y_pos += line_height + 5
    
    # Fatigue level
    fatigue_level = metrics.get("fatigue_level", "unknown").upper()
    cv2.putText(frame, f"LEVEL: {fatigue_level}", (20, y_pos), font, font_scale, fatigue_color, thickness)
    y_pos += line_height + 10
    
    # Blink rate
    blink_rate = metrics.get("blink_rate", 0.0)
            cv2.putText(frame, f"Blink Rate: {blink_rate:.1f}/min", (20, y_pos), 
               font, font_scale, color_text, thickness)
    y_pos += line_height
    
    # PERCLOS (eye closure) - shows percentage of time eyes are closed
    perclos = metrics.get("perclos", 0.0)
    perclos_color = color_good if perclos < 0.2 else (color_warning if perclos < 0.5 else color_danger)
    cv2.putText(frame, f"Eye Closure: {perclos:.1%}", (20, y_pos), 
               font, font_scale, perclos_color, thickness)
    y_pos += line_height
    
    # EAR value (for calibration/debugging)
    current_ear = metrics.get("current_ear", 0.0)
    if current_ear > 0:  # Only show if available
        ear_status = "OPEN" if current_ear > 0.25 else "CLOSED"
        ear_color = color_good if current_ear > 0.25 else color_warning
        cv2.putText(frame, f"EAR: {current_ear:.3f} ({ear_status})", (20, y_pos), 
                   font, font_scale - 0.1, ear_color, 1)
        y_pos += line_height
    
    # Yawn count
    yawn_count = metrics.get("yawn_count_5min", metrics.get("yawn_count", 0))
    cv2.putText(frame, f"Yawns (5min): {yawn_count}", (20, y_pos), 
               font, font_scale, color_text, thickness)
    y_pos += line_height
    
    # Gaze stability
    gaze_stability = metrics.get("gaze_stability", 0.0)
    gaze_color = color_good if gaze_stability > 0.7 else (color_warning if gaze_stability > 0.4 else color_danger)
    cv2.putText(frame, f"Gaze Stability: {gaze_stability:.2f}", (20, y_pos), 
               font, font_scale, gaze_color, thickness)
    y_pos += line_height
    
    # Fidget score
    fidget_score = metrics.get("fidgeting_score", metrics.get("fidget_score", 0.0))
    cv2.putText(frame, f"Fidget Score: {fidget_score:.2f}", (20, y_pos), 
               font, font_scale, color_text, thickness)
    y_pos += line_height
    
    # Neck cracks
    neck_cracks = metrics.get("neck_crack_count_1min", 0)
    if neck_cracks > 0:
        cv2.putText(frame, f"Neck Cracks: {neck_cracks}", (20, y_pos), 
                   font, font_scale, color_warning, thickness)
        y_pos += line_height
    
    # Recommendation
    recommendation = metrics.get("recommendation", "continue")
    rec_text = recommendation.replace("_", " ").upper()
    rec_color = color_good if "continue" in recommendation else color_warning
    y_pos += 10
    cv2.putText(frame, f"REC: {rec_text}", (20, y_pos), 
               font, font_scale, rec_color, thickness)
    
    # Draw face bounding box if available (we'd need to expose this from C++)
    # For now, just show detection status
    
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


@app.websocket("/ws/fatigue-detect")
async def fatigue_websocket(websocket: WebSocket):
    """WebSocket endpoint that streams fatigue metrics (JSON only)."""
    # Accept all origins for WebSocket (CORS doesn't apply to WS, but we need to accept)
    await websocket.accept()
    active_connections.add(websocket)
    
    print(f"[INFO] New WebSocket connection. Total connections: {len(active_connections)}")
    
    last_pvt_time = 0
    pvt_cooldown_ms = 10000  # 10 seconds between PVT challenges
    
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
                # Process frame - the display thread also processes, but for WebSocket
                # we want fresh processing. Alternatively, we could share the result.
                # For now, process separately (will be fast enough with optimizations)
                metrics = engine.process_frame(frame, timestamp_ms)
                
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
            await websocket.send_json({
                "type": "metrics",
                "timestamp": timestamp_ms,
                "data": metrics
            })
            
            # 4. Check for PVT challenge trigger
            fatigue_score = metrics.get("fatigue_score", 0.0)
            current_time_ms = timestamp_ms
            
            if (fatigue_score >= 0.7 and 
                (current_time_ms - last_pvt_time) > pvt_cooldown_ms and
                active_connections.__contains__(websocket)):  # Only send to this connection
                
                delay_ms = random.randint(1000, 5000)
                await websocket.send_json({
                    "type": "pvt_challenge",
                    "delay_ms": delay_ms,
                    "triggered_by_fatigue_score": fatigue_score
                })
                last_pvt_time = current_time_ms
            
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
        active_connections.discard(websocket)
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
    """Handle PVT challenge response from frontend."""
    if reaction_time_ms < 0:
        return {"status": "error", "message": "Invalid reaction time"}
    
    # Interpret reaction time
    if reaction_time_ms < 250:
        interpretation = "alert"  # False alarm, reset fatigue
    elif reaction_time_ms <= 500:
        interpretation = "normal"
    elif reaction_time_ms <= 1000:
        interpretation = "impaired"
    else:
        interpretation = "severely_impaired"
    
    # If severely impaired, could update fatigue score here
    
    return {
        "status": "ok",
        "interpretation": interpretation,
        "reaction_time_ms": reaction_time_ms
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
