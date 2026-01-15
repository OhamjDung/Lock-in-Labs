"""
Recording Script for Fatigue Detection Examples
Records video clips with labels for neck cracks and yawns.
"""

import cv2
import numpy as np
import os
import time
import json
from pathlib import Path
from datetime import datetime

# Output directory
EXAMPLES_DIR = Path(__file__).parent / "examples"
EXAMPLES_DIR.mkdir(exist_ok=True)

# Subdirectories
NECK_CRACK_DIR = EXAMPLES_DIR / "neck_cracks"
YAWN_DIR = EXAMPLES_DIR / "yawns"
NECK_CRACK_DIR.mkdir(exist_ok=True)
YAWN_DIR.mkdir(exist_ok=True)

# Recording settings
FPS = 30
PRE_RECORD_SECONDS = 2  # Record 2 seconds before trigger
POST_RECORD_SECONDS = 2  # Record 2 seconds after trigger
BUFFER_SIZE = FPS * (PRE_RECORD_SECONDS + POST_RECORD_SECONDS)


class ExampleRecorder:
    def __init__(self, camera_index=0):
        self.camera = cv2.VideoCapture(camera_index)
        if not self.camera.isOpened():
            raise RuntimeError(f"Failed to open camera {camera_index}")
        
        # Get camera properties
        self.width = int(self.camera.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.camera.get(cv2.CAP_PROP_FRAME_HEIGHT))
        
        # Frame buffer
        self.frame_buffer = []
        self.buffer_index = 0
        
        # Recording state
        self.recording_type = None  # "neck_crack" or "yawn"
        self.recording_frames = []
        self.recording_start_time = None
        self.is_recording = False  # Track if currently recording
        
    def add_frame_to_buffer(self, frame):
        """Add frame to circular buffer."""
        if len(self.frame_buffer) < BUFFER_SIZE:
            self.frame_buffer.append(frame.copy())
        else:
            self.frame_buffer[self.buffer_index] = frame.copy()
            self.buffer_index = (self.buffer_index + 1) % BUFFER_SIZE
    
    def start_recording(self, recording_type):
        """Start recording (saves buffer + future frames)."""
        if self.is_recording:
            # Already recording - stop and save
            self.stop_recording()
            return
        
        self.recording_type = recording_type
        self.recording_frames = []
        self.recording_start_time = time.time()
        self.is_recording = True
        
        # Copy buffer (last PRE_RECORD_SECONDS of frames)
        buffer_start = max(0, self.buffer_index - (FPS * PRE_RECORD_SECONDS))
        if buffer_start < self.buffer_index:
            self.recording_frames.extend(self.frame_buffer[buffer_start:self.buffer_index])
        else:
            # Wrap around case
            self.recording_frames.extend(self.frame_buffer[buffer_start:])
            self.recording_frames.extend(self.frame_buffer[:self.buffer_index])
        
        print(f"[RECORDING] Started recording {recording_type} - Press {recording_type[0].upper()} again to stop")
    
    def stop_recording(self):
        """Stop recording and save."""
        if not self.is_recording:
            return
        
        self.is_recording = False
        self.save_recording()
    
    def add_recording_frame(self, frame):
        """Add frame to current recording."""
        if not self.is_recording:
            return
        
        self.recording_frames.append(frame.copy())
    
    def save_recording(self):
        """Save recording to file."""
        if self.recording_type is None or len(self.recording_frames) == 0:
            return
        
        # Determine output directory
        if self.recording_type == "neck_crack":
            output_dir = NECK_CRACK_DIR
        elif self.recording_type == "yawn":
            output_dir = YAWN_DIR
        else:
            print(f"[ERROR] Unknown recording type: {self.recording_type}")
            return
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]
        video_path = output_dir / f"{self.recording_type}_{timestamp}.mp4"
        metadata_path = output_dir / f"{self.recording_type}_{timestamp}.json"
        
        # Save video
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(str(video_path), fourcc, FPS, (self.width, self.height))
        
        for frame in self.recording_frames:
            out.write(frame)
        
        out.release()
        
        # Save metadata
        metadata = {
            "type": self.recording_type,
            "timestamp": timestamp,
            "frame_count": len(self.recording_frames),
            "fps": FPS,
            "resolution": [self.width, self.height],
            "pre_record_seconds": PRE_RECORD_SECONDS,
            "post_record_seconds": POST_RECORD_SECONDS
        }
        
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"[SAVED] {self.recording_type} example: {video_path.name} ({len(self.recording_frames)} frames)")
        
        # Reset
        self.recording_type = None
        self.recording_frames = []
        self.recording_start_time = None
    
    def release(self):
        """Release camera."""
        if self.camera.isOpened():
            self.camera.release()


def main():
    print("=" * 60)
    print("Fatigue Detection Example Recorder")
    print("=" * 60)
    print(f"Examples will be saved to: {EXAMPLES_DIR}")
    print(f"  - Neck cracks: {NECK_CRACK_DIR}")
    print(f"  - Yawns: {YAWN_DIR}")
    print()
    print("Controls:")
    print("  'N' or 'n' - Start/Stop neck crack recording")
    print("  'Y' or 'y' - Start/Stop yawn recording")
    print("  'Q' or 'q' - Quit")
    print()
    print("Instructions:")
    print("  1. Position yourself in front of the camera")
    print("  2. Press 'N' to START recording, perform neck crack, press 'N' again to STOP")
    print("  3. Press 'Y' to START recording, perform yawn, press 'Y' again to STOP")
    print("  4. The system saves 2 seconds before start + all frames until stop")
    print()
    print("=" * 60)
    
    recorder = ExampleRecorder()
    
    try:
        frame_time = 1.0 / FPS
        last_frame_time = time.time()
        
        while True:
            ret, frame = recorder.camera.read()
            if not ret:
                print("[ERROR] Failed to read frame")
                break
            
            current_time = time.time()
            
            # Maintain frame rate
            elapsed = current_time - last_frame_time
            if elapsed < frame_time:
                time.sleep(frame_time - elapsed)
            
            last_frame_time = time.time()
            
            # Add to buffer
            recorder.add_frame_to_buffer(frame)
            
            # Add to current recording if active
            recorder.add_recording_frame(frame)
            
            # Draw overlay
            overlay = frame.copy()
            cv2.putText(overlay, "Example Recorder", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)
            
            if recorder.is_recording:
                cv2.putText(overlay, f"RECORDING: {recorder.recording_type.upper()}", (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 0, 255), 3)
                elapsed = time.time() - recorder.recording_start_time
                cv2.putText(overlay, f"Time: {elapsed:.1f}s - Press {recorder.recording_type[0].upper()} to STOP", (10, 110),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
            else:
                cv2.putText(overlay, "Press 'N' to START neck crack, 'Y' to START yawn", (10, 70),
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.putText(overlay, "Press 'Q' to quit", (10, overlay.shape[0] - 20),
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            cv2.imshow("Example Recorder", overlay)
            
            # Handle keyboard input
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q') or key == ord('Q'):
                # Stop any active recording before quitting
                if recorder.is_recording:
                    recorder.stop_recording()
                break
            elif key == ord('n') or key == ord('N'):
                recorder.start_recording("neck_crack")
            elif key == ord('y') or key == ord('Y'):
                recorder.start_recording("yawn")
    
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        recorder.release()
        cv2.destroyAllWindows()
        print(f"\n[INFO] Recording complete. Examples saved to: {EXAMPLES_DIR}")


if __name__ == "__main__":
    main()
