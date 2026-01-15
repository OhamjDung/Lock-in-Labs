"""
MediaPipe Vision System
Processes camera frames using Google MediaPipe Face Landmarker to extract facial landmarks and metrics.
"""

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from mediapipe import ImageFormat
import numpy as np
from typing import Optional, Dict, Any
import time
import os
import urllib.request

# MediaPipe 468-point landmark indices
# Left Eye (6 points for EAR calculation)
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
# Right Eye (6 points for EAR calculation)
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]
# Mouth landmarks for MAR calculation
# Upper lip top, lower lip bottom, left corner, right corner
MOUTH_INDICES = [13, 14, 61, 291, 39, 181, 0, 17, 269, 405]
# Nose tip for head pose
NOSE_TIP_INDEX = 1
# Face oval for bounding box
FACE_OVAL_INDICES = [10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288, 397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136, 172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109]

# MediaPipe Face Landmarker model URL
FACE_LANDMARKER_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task"


def _get_model_path() -> str:
    """
    Get the path to the MediaPipe Face Landmarker model.
    Downloads the model if it doesn't exist.
    """
    # Try to find model in common locations
    model_dir = os.path.join(os.path.dirname(__file__), "..", "models")
    os.makedirs(model_dir, exist_ok=True)
    model_path = os.path.join(model_dir, "face_landmarker.task")
    
    # Download model if it doesn't exist
    if not os.path.exists(model_path):
        print(f"[MediaPipe] Downloading Face Landmarker model to {model_path}...")
        print("[MediaPipe] This may take a few minutes on first run...")
        try:
            urllib.request.urlretrieve(FACE_LANDMARKER_MODEL_URL, model_path)
            print("[MediaPipe] Model downloaded successfully!")
        except Exception as e:
            print(f"[MediaPipe] Error downloading model: {e}")
            print("[MediaPipe] Please download manually from:")
            print(f"[MediaPipe] {FACE_LANDMARKER_MODEL_URL}")
            raise
    
    return model_path


class VisionSystem:
    """
    MediaPipe-based vision system for face tracking and metric extraction.
    
    This replaces the C++ Dlib/YuNet code with Google MediaPipe for:
    - Better stability with glasses
    - Better rotation handling (up to 90 degrees)
    - Reduced jitter (temporal filtering built-in)
    - Simpler integration (pure Python)
    """
    
    def __init__(self, 
                 max_num_faces: int = 1,
                 refine_landmarks: bool = True,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        """
        Initialize MediaPipe Face Landmarker.
        
        Args:
            max_num_faces: Maximum number of faces to detect (default: 1)
            refine_landmarks: Enable iris tracking for better gaze estimation (default: True)
            min_detection_confidence: Minimum confidence for face detection (default: 0.5)
            min_tracking_confidence: Minimum confidence for face tracking (default: 0.5)
        """
        # Get model path (download if needed)
        model_path = _get_model_path()
        
        # Create FaceLandmarker options
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=False,
            running_mode=vision.RunningMode.IMAGE,  # Process single images
            num_faces=max_num_faces,
            min_face_detection_confidence=min_detection_confidence,
            min_face_presence_confidence=min_tracking_confidence,
            min_tracking_confidence=min_tracking_confidence
        )
        
        # Create FaceLandmarker
        
        # Gaze calibration (min/max values for normalization)
        # Initialize to extreme values so min/max will work correctly
        self.gaze_x_min = float('inf')  # Will be set to minimum raw value
        self.gaze_x_max = float('-inf')  # Will be set to maximum raw value
        self.gaze_y_min = float('inf')  # Will be set to minimum raw value
        self.gaze_y_max = float('-inf')  # Will be set to maximum raw value
        self.gaze_calibrated = False  # True when all 4 directions are calibrated
        self.face_landmarker = vision.FaceLandmarker.create_from_options(options)
        
        # Tracking state
        self.last_face_bbox = None
        self.frame_count = 0
        
    def process(self, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """
        Process a single frame and extract facial metrics.
        
        Args:
            frame: BGR image frame from OpenCV
            
        Returns:
            Dictionary with metrics:
            - face_detected: bool
            - ear: float (Eye Aspect Ratio, average of both eyes)
            - left_ear: float
            - right_ear: float
            - mar: float (Mouth Aspect Ratio)
            - gaze_x: float (head yaw, normalized -0.5 to 0.5)
            - gaze_y: float (head pitch, normalized -0.5 to 0.5)
            - face_bbox: tuple (x, y, w, h)
            - landmarks: MediaPipe face mesh object (optional, for drawing)
        """
        if frame is None or frame.size == 0:
            return None
            
        h, w = frame.shape[:2]
        
        # Convert BGR to RGB (MediaPipe expects RGB)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        
        # Create MediaPipe Image
        mp_image = mp.Image(image_format=ImageFormat.SRGB, data=rgb_frame)
        
        # Process frame
        detection_result = self.face_landmarker.detect(mp_image)
        
        # Initialize head pose variables
        head_pitch = 0.0
        head_yaw = 0.0
        head_roll = 0.0
        
        # Check if face detected
        if not detection_result.face_landmarks or len(detection_result.face_landmarks) == 0:
            self.last_face_bbox = None
            return {
                "face_detected": False,
                "ear": 0.0,
                "left_ear": 0.0,
                "right_ear": 0.0,
                "mar": 0.0,
                "gaze_x": 0.0,
                "gaze_y": 0.0,
                "head_pitch": head_pitch,
                "head_yaw": head_yaw,
                "head_roll": head_roll,
                "face_bbox": None,
                "landmarks": None
            }
        
        # Get first face (we only track one)
        landmarks = detection_result.face_landmarks[0]
        
        # Helper function to convert normalized coordinates to pixel coordinates
        def get_pt(idx: int) -> np.ndarray:
            """Get pixel coordinates for landmark index."""
            if idx >= len(landmarks):
                return np.array([0.0, 0.0])
            pt = landmarks[idx]
            return np.array([pt.x * w, pt.y * h])
        
        # 1. Calculate EAR (Eye Aspect Ratio) for both eyes
        def calc_ear(indices: list) -> float:
            """
            Calculate Eye Aspect Ratio using 6-point method.
            
            EAR = (vertical_dist_1 + vertical_dist_2) / (2 * horizontal_dist)
            """
            # Vertical distances (top and bottom of eye)
            vertical_1 = np.linalg.norm(get_pt(indices[1]) - get_pt(indices[5]))
            vertical_2 = np.linalg.norm(get_pt(indices[2]) - get_pt(indices[4]))
            # Horizontal distance (eye width)
            horizontal = np.linalg.norm(get_pt(indices[0]) - get_pt(indices[3]))
            
            if horizontal == 0:
                return 0.0
            
            ear = (vertical_1 + vertical_2) / (2.0 * horizontal)
            return ear
        
        left_ear = calc_ear(LEFT_EYE_INDICES)
        right_ear = calc_ear(RIGHT_EYE_INDICES)
        avg_ear = (left_ear + right_ear) / 2.0
        
        # 2. Calculate MAR (Mouth Aspect Ratio)
        def calc_mar() -> float:
            """
            Calculate Mouth Aspect Ratio.
            
            MAR = vertical_mouth_distance / horizontal_mouth_distance
            """
            # Upper lip top (index 13) and lower lip bottom (index 14)
            vertical_dist = np.linalg.norm(get_pt(13) - get_pt(14))
            # Mouth corners (indices 61 and 291)
            horizontal_dist = np.linalg.norm(get_pt(61) - get_pt(291))
            
            if horizontal_dist == 0:
                return 0.0
            
            mar = vertical_dist / horizontal_dist
            return mar
        
        mar = calc_mar()
        
        # 3. Calculate Head Pose (Gaze direction and rotation angles)
        # MediaPipe gives us 3D coordinates (z-axis), making pose estimation easier
        if len(landmarks) > NOSE_TIP_INDEX:
            nose_tip = landmarks[NOSE_TIP_INDEX]
            # Calculate gaze based on nose position relative to face center
            # Use face center from eye positions for better accuracy
            def get_landmark_pt_norm(idx):
                if idx < len(landmarks):
                    pt = landmarks[idx]
                    return np.array([pt.x, pt.y])
                return np.array([0.5, 0.5])  # Default to center if not found
            
            # Get eye centers for face center calculation
            left_eye_center_norm = np.mean([get_landmark_pt_norm(i) for i in LEFT_EYE_INDICES], axis=0)
            right_eye_center_norm = np.mean([get_landmark_pt_norm(i) for i in RIGHT_EYE_INDICES], axis=0)
            face_center_norm = (left_eye_center_norm + right_eye_center_norm) / 2.0
            
            # Gaze is relative to face center
            nose_pos = np.array([nose_tip.x, nose_tip.y])
            gaze_offset = nose_pos - face_center_norm
            
            # Calculate raw gaze (multiply by 2 to increase sensitivity)
            raw_gaze_x = gaze_offset[0] * 2.0
            raw_gaze_y = gaze_offset[1] * 2.0
            
            # Apply calibration if available
            if self.gaze_calibrated:
                # Normalize to -0.5 to 0.5 range using calibrated min/max
                # Map from [gaze_x_min, gaze_x_max] to [-0.5, 0.5]
                x_range = self.gaze_x_max - self.gaze_x_min
                y_range = self.gaze_y_max - self.gaze_y_min
                if x_range > 0:
                    gaze_x = ((raw_gaze_x - self.gaze_x_min) / x_range - 0.5) * 1.0
                else:
                    gaze_x = 0.0
                if y_range > 0:
                    gaze_y = ((raw_gaze_y - self.gaze_y_min) / y_range - 0.5) * 1.0
                else:
                    gaze_y = 0.0
                gaze_x = np.clip(gaze_x, -0.5, 0.5)
                gaze_y = np.clip(gaze_y, -0.5, 0.5)
            else:
                # Use default clipping if not calibrated
                gaze_x = np.clip(raw_gaze_x, -0.5, 0.5)
                gaze_y = np.clip(raw_gaze_y, -0.5, 0.5)
            
            # Calculate head rotation angles (pitch, yaw, roll) for neck crack detection
            # Use MediaPipe landmark indices for head pose calculation
            # Left eye center: average of left eye landmarks
            # Right eye center: average of right eye landmarks
            # Mouth corners: for roll calculation
            
            def get_landmark_pt(idx):
                """Get pixel coordinates for landmark index."""
                if idx < len(landmarks):
                    pt = landmarks[idx]
                    return np.array([pt.x * w, pt.y * h])
                return np.array([w/2.0, h/2.0])  # Default to center if not found
            
            # Eye centers (using key points from MediaPipe)
            # Left eye: 33, 133, 157, 158, 159, 160
            # Right eye: 362, 263, 387, 388, 389, 390
            left_eye_pts = [get_landmark_pt(33), get_landmark_pt(133), get_landmark_pt(157)]
            right_eye_pts = [get_landmark_pt(362), get_landmark_pt(263), get_landmark_pt(387)]
            
            left_eye_center = np.mean(left_eye_pts, axis=0)
            right_eye_center = np.mean(right_eye_pts, axis=0)
            eye_center = (left_eye_center + right_eye_center) / 2.0
            
            # Nose tip
            nose_pt = get_landmark_pt(NOSE_TIP_INDEX)
            
            # Mouth corners (for roll)
            mouth_left = get_landmark_pt(61)  # Left mouth corner
            mouth_right = get_landmark_pt(291)  # Right mouth corner
            
            # Calculate angles (in degrees)
            # Yaw (left-right): horizontal angle based on eye line relative to horizontal
            eye_line = right_eye_center - left_eye_center
            eye_line_length = np.linalg.norm(eye_line)
            if eye_line_length > 0:
                # Calculate angle from horizontal (0 degrees = straight ahead)
                head_yaw = np.arctan2(eye_line[1], eye_line[0]) * 180.0 / np.pi
                # Normalize to -90 to 90 degrees
                if head_yaw > 90:
                    head_yaw -= 180
                elif head_yaw < -90:
                    head_yaw += 180
            else:
                head_yaw = 0.0
            
            # Pitch (up-down): vertical angle based on nose position relative to eye center
            nose_vec = nose_pt - eye_center
            nose_vec_length = np.linalg.norm(nose_vec)
            if nose_vec_length > 0:
                # Positive pitch = looking down, negative = looking up
                head_pitch = np.arcsin(nose_vec[1] / nose_vec_length) * 180.0 / np.pi
            else:
                head_pitch = 0.0
            
            # Roll (tilt): angle of eye line from horizontal (tilt left/right)
            if eye_line_length > 0:
                # Calculate angle of eye line from horizontal
                eye_angle = np.arctan2(eye_line[1], eye_line[0]) * 180.0 / np.pi
                # Normalize roll to -45 to 45 degrees
                head_roll = eye_angle
                if head_roll > 45:
                    head_roll -= 90
                elif head_roll < -45:
                    head_roll += 90
            else:
                head_roll = 0.0
        else:
            gaze_x = 0.0
            gaze_y = 0.0
            raw_gaze_x = 0.0
            raw_gaze_y = 0.0
            head_pitch = 0.0
            head_yaw = 0.0
            head_roll = 0.0
        
        # 4. Calculate Face Bounding Box from face oval landmarks
        def calc_face_bbox() -> tuple:
            """Calculate bounding box from face oval landmarks."""
            x_coords = []
            y_coords = []
            for idx in FACE_OVAL_INDICES:
                if idx < len(landmarks):
                    x_coords.append(landmarks[idx].x * w)
                    y_coords.append(landmarks[idx].y * h)
            
            if not x_coords or not y_coords:
                return (0, 0, 0, 0)
            
            x_min = int(min(x_coords))
            x_max = int(max(x_coords))
            y_min = int(min(y_coords))
            y_max = int(max(y_coords))
            
            return (x_min, y_min, x_max - x_min, y_max - y_min)
        
        face_bbox = calc_face_bbox()
        self.last_face_bbox = face_bbox
        
        self.frame_count += 1
        
        return {
            "face_detected": True,
            "ear": avg_ear,
            "left_ear": left_ear,
            "right_ear": right_ear,
            "mar": mar,
            "gaze_x": gaze_x,
            "gaze_y": gaze_y,
            "raw_gaze_x": raw_gaze_x,  # Raw values for calibration
            "raw_gaze_y": raw_gaze_y,
            "head_pitch": head_pitch,
            "head_yaw": head_yaw,
            "head_roll": head_roll,
            "face_bbox": face_bbox,
            "landmarks": landmarks  # Optional: for drawing/debugging
        }
    
    def draw_landmarks(self, frame: np.ndarray, results: Dict[str, Any]) -> np.ndarray:
        """
        Draw MediaPipe landmarks on frame for debugging/visualization.
        
        Args:
            frame: BGR image frame
            results: Results dictionary from process()
            
        Returns:
            Frame with landmarks drawn
        """
        if not results.get("face_detected") or results.get("landmarks") is None:
            return frame
        
        landmarks = results["landmarks"]
        h, w = frame.shape[:2]
        
        # Draw key landmarks as circles
        # Draw eye landmarks
        for idx in LEFT_EYE_INDICES + RIGHT_EYE_INDICES:
            if idx < len(landmarks):
                pt = landmarks[idx]
                x, y = int(pt.x * w), int(pt.y * h)
                cv2.circle(frame, (x, y), 2, (0, 255, 0), -1)
        
        # Draw mouth landmarks
        for idx in MOUTH_INDICES:
            if idx < len(landmarks):
                pt = landmarks[idx]
                x, y = int(pt.x * w), int(pt.y * h)
                cv2.circle(frame, (x, y), 2, (255, 0, 0), -1)
        
        # Draw nose tip
        if NOSE_TIP_INDEX < len(landmarks):
            pt = landmarks[NOSE_TIP_INDEX]
            x, y = int(pt.x * w), int(pt.y * h)
            cv2.circle(frame, (x, y), 3, (0, 0, 255), -1)
        
        # Draw bounding box
        if results.get("face_bbox"):
            x, y, w, h = results["face_bbox"]
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
        
        # Draw metrics text
        y_pos = 30
        cv2.putText(frame, f"EAR: {results['ear']:.3f}", (10, y_pos), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_pos += 25
        cv2.putText(frame, f"MAR: {results['mar']:.3f}", (10, y_pos), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_pos += 25
        cv2.putText(frame, f"Gaze: ({results['gaze_x']:.2f}, {results['gaze_y']:.2f})", 
                   (10, y_pos), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        return frame
    
    def calibrate_gaze(self, direction: str, raw_gaze_x: float, raw_gaze_y: float):
        """
        Calibrate gaze range for a specific direction.
        
        Args:
            direction: "left", "right", "up", or "down"
            raw_gaze_x: Raw gaze X value (before calibration)
            raw_gaze_y: Raw gaze Y value (before calibration)
        """
        # The coordinate system appears to be inverted based on user feedback
        # So we need to track min/max correctly
        if direction == "left":
            # Store the actual raw value (may be positive or negative)
            self.gaze_x_min = min(self.gaze_x_min, raw_gaze_x)
        elif direction == "right":
            # Store the actual raw value (may be positive or negative)
            self.gaze_x_max = max(self.gaze_x_max, raw_gaze_x)
        elif direction == "up":
            # Store the actual raw value
            self.gaze_y_min = min(self.gaze_y_min, raw_gaze_y)
        elif direction == "down":
            # Store the actual raw value
            self.gaze_y_max = max(self.gaze_y_max, raw_gaze_y)
        
        # After all 4 directions are captured, ensure min < max (swap if needed)
        if self.gaze_x_min != float('inf') and self.gaze_x_max != float('-inf'):
            if self.gaze_x_min > self.gaze_x_max:
                # Swap them
                self.gaze_x_min, self.gaze_x_max = self.gaze_x_max, self.gaze_x_min
        
        if self.gaze_y_min != float('inf') and self.gaze_y_max != float('-inf'):
            if self.gaze_y_min > self.gaze_y_max:
                # Swap them
                self.gaze_y_min, self.gaze_y_max = self.gaze_y_max, self.gaze_y_min
        
        # Check if all directions are calibrated (have valid ranges)
        if (self.gaze_x_min != float('inf') and self.gaze_x_max != float('-inf') and
            self.gaze_y_min != float('inf') and self.gaze_y_max != float('-inf') and
            self.gaze_x_min < self.gaze_x_max and 
            self.gaze_y_min < self.gaze_y_max):
            self.gaze_calibrated = True
    
    def get_gaze_calibration(self) -> Dict[str, Any]:
        """Get current gaze calibration values."""
        return {
            "gaze_x_min": self.gaze_x_min,
            "gaze_x_max": self.gaze_x_max,
            "gaze_y_min": self.gaze_y_min,
            "gaze_y_max": self.gaze_y_max,
            "calibrated": self.gaze_calibrated
        }
    
    def reset_gaze_calibration(self):
        """Reset gaze calibration to defaults."""
        self.gaze_x_min = float('inf')
        self.gaze_x_max = float('-inf')
        self.gaze_y_min = float('inf')
        self.gaze_y_max = float('-inf')
        self.gaze_calibrated = False
    
    def release(self):
        """Release MediaPipe resources."""
        if hasattr(self, 'face_landmarker'):
            self.face_landmarker.close()
            self.face_landmarker = None
