"""
Three-Gate Live Debug Overlay Test
Real-time visualization of all three gates with debugging information.

This script connects to the fatigue detection daemon and displays a live video feed
with an overlay showing:
  - Gate 1 (Context): Active window and multiplier
  - Gate 2 (Focus): Gaze position and focus status
  - Gate 3 (Fatigue): Fatigue score and multiplier
  - Lock-In Score: Combined score from all three gates

Run this after starting the daemon:
  python -m fatigue_detection.app
Then in another terminal:
  python fatigue_detection/test_debug_overlay.py
"""

import asyncio
import cv2
import json
import numpy as np
import websockets
import threading
from collections import deque
from datetime import datetime


class DebugOverlayTester:
    """Live debug overlay for three-gate system."""
    
    def __init__(self):
        self.latest_metrics = {
            "active_window": "Waiting...",
            "context_multiplier": 0.0,
            "looking_at_screen": False,
            "focus_multiplier": 0.0,
            "fatigue_multiplier": 0.0,
            "lock_in_score": 0.0,
            "fatigue_score": 0.0,
            "face_detected": False,
            "gaze_x": 0.0,
            "gaze_y": 0.0,
            "ear": 0.0,
            "mar": 0.0,
            "blink_rate": 0,
            "head_yaw": 0.0,
            "head_pitch": 0.0,
        }
        self.lock = threading.Lock()
        self.running = True
        self.frame_count = 0
        self.fps_history = deque(maxlen=30)
        self.last_time = None
        
    async def websocket_listener(self):
        """Connect to WebSocket and listen for metrics."""
        uri = "ws://127.0.0.1:8000/ws/fatigue-detect"
        
        print(f"\n[WS] Connecting to {uri}...")
        
        retry_count = 0
        max_retries = 3  # Reduced retries
        
        while self.running and retry_count < max_retries:
            try:
                async with websockets.connect(uri, ping_interval=None) as websocket:
                    print("[WS] ✅ Connected to daemon!")
                    retry_count = 0  # Reset on successful connection
                    message_count = 0
                    
                    while self.running:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                            data = json.loads(message)
                            message_count += 1
                            
                            if message_count % 30 == 0:  # Print every 30 messages
                                print(f"[WS] Received {message_count} messages...")
                            
                            if data.get("type") == "metrics":
                                with self.lock:
                                    self.latest_metrics.update(data.get("data", {}))
                            elif data.get("type") == "error":
                                print(f"[WS] Server error: {data.get('message')}")
                            
                        except asyncio.TimeoutError:
                            print(f"[WS] ⚠️  No data received in 5 seconds (total messages: {message_count})")
                            continue
                        except websockets.exceptions.ConnectionClosed as e:
                            print(f"[WS] Connection closed: {e}")
                            break
                        except Exception as e:
                            print(f"[WS] Receive error: {e}")
                            break
                        
            except Exception as e:
                retry_count += 1
                if retry_count < max_retries:
                    print(f"[WS] ⚠️  Connection failed (attempt {retry_count}/{max_retries}): {e}")
                    print(f"[WS] Retrying in 2 seconds...")
                    await asyncio.sleep(2)
                else:
                    print(f"[WS] ❌ Max retries reached. Check if daemon is running: python -m fatigue_detection.app")
                    self.running = False
                    break
    
    def draw_gate_panel(self, frame, x, y, title, color, values):
        """Draw a colored panel with gate information."""
        font = cv2.FONT_HERSHEY_SIMPLEX
        font_scale = 0.6
        font_thickness = 1
        line_height = 28
        
        # Panel background
        panel_width = 320
        panel_height = 20 + len(values) * line_height
        cv2.rectangle(frame, (x, y), (x + panel_width, y + panel_height), color, -1)
        cv2.rectangle(frame, (x, y), (x + panel_width, y + panel_height), (255, 255, 255), 2)
        
        # Title
        cv2.putText(frame, title, (x + 10, y + 20), font, font_scale * 1.2, 
                    (255, 255, 255), font_thickness + 1)
        
        # Values
        for i, (label, value) in enumerate(values):
            text = f"{label}: {value}"
            y_pos = y + 25 + (i + 1) * line_height
            cv2.putText(frame, text, (x + 15, y_pos), font, font_scale, 
                        (255, 255, 255), font_thickness)
    
    def draw_overlay(self, frame):
        """Draw all debugging information on frame."""
        height, width = frame.shape[:2]
        
        # Semi-transparent dark background for text
        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (width, height), (0, 0, 0), -1)
        frame = cv2.addWeighted(frame, 0.3, overlay, 0.7, 0)
        
        with self.lock:
            metrics = self.latest_metrics.copy()
        
        # Calculate FPS
        current_time = datetime.now()
        if self.last_time:
            dt = (current_time - self.last_time).total_seconds()
            if dt > 0:
                fps = 1.0 / dt
                self.fps_history.append(fps)
        self.last_time = current_time
        
        avg_fps = np.mean(list(self.fps_history)) if self.fps_history else 0
        self.frame_count += 1
        
        # ============================================================
        # GATE 1: CONTEXT (Top-left)
        # ============================================================
        context_mult = metrics["context_multiplier"]
        context_color = (0, 255, 0) if context_mult > 0.5 else (0, 165, 255) if context_mult > 0 else (0, 0, 255)
        
        window_short = metrics["active_window"][:35] if len(metrics["active_window"]) > 35 else metrics["active_window"]
        gate1_values = [
            ("Window", window_short),
            ("Multiplier", f"{context_mult:.2f}"),
            ("Status", "🔓 PRODUCTIVE" if context_mult >= 1.0 else "⚠️  AMBIGUOUS" if context_mult >= 0.5 else "🔒 DISTRACTED"),
        ]
        self.draw_gate_panel(frame, 10, 10, "GATE 1: CONTEXT", context_color, gate1_values)
        
        # ============================================================
        # GATE 2: FOCUS (Top-right)
        # ============================================================
        looking = metrics["looking_at_screen"]
        focus_mult = metrics["focus_multiplier"]
        focus_color = (0, 255, 0) if looking else (0, 0, 255)
        
        gaze_region = "CENTER" if abs(metrics["gaze_x"]) < 0.3 and abs(metrics["gaze_y"]) < 0.3 else \
                      ("LEFT" if metrics["gaze_x"] < -0.3 else "RIGHT" if metrics["gaze_x"] > 0.3 else "") + \
                      ("TOP" if metrics["gaze_y"] < -0.3 else "BOTTOM" if metrics["gaze_y"] > 0.3 else "")
        gaze_region = gaze_region or "EDGE"
        
        gate2_values = [
            ("Looking at Screen", "✓ YES" if looking else "✗ NO"),
            ("Gaze Position", f"({metrics['gaze_x']:.2f}, {metrics['gaze_y']:.2f})"),
            ("Region", gaze_region),
            ("Multiplier", f"{focus_mult:.2f}"),
        ]
        self.draw_gate_panel(frame, width - 330, 10, "GATE 2: FOCUS", focus_color, gate2_values)
        
        # ============================================================
        # GATE 3: FATIGUE (Bottom-left)
        # ============================================================
        fatigue_score = metrics["fatigue_score"]
        fatigue_mult = metrics["fatigue_multiplier"]
        
        # Fatigue color: green (alert) → yellow (moderate) → red (severe)
        if fatigue_mult >= 0.7:
            fatigue_color = (0, 255, 0)
        elif fatigue_mult >= 0.4:
            fatigue_color = (0, 165, 255)
        else:
            fatigue_color = (0, 0, 255)
        
        gate3_values = [
            ("Fatigue Score", f"{fatigue_score:.2f}"),
            ("Multiplier", f"{fatigue_mult:.2f}"),
            ("Blink Rate", f"{metrics.get('blink_rate', 0)} bpm"),
            ("Status", "😴 ALERT" if fatigue_mult >= 0.7 else "⚠️  MODERATE" if fatigue_mult >= 0.4 else "🚨 SEVERE"),
        ]
        self.draw_gate_panel(frame, 10, height - 140, "GATE 3: FATIGUE", fatigue_color, gate3_values)
        
        # ============================================================
        # LOCK-IN SCORE (Bottom-right)
        # ============================================================
        lock_in_score = metrics["lock_in_score"]
        
        if lock_in_score >= 0.7:
            status = "🟢 LOCKED IN"
            color = (0, 255, 0)
        elif lock_in_score >= 0.4:
            status = "🟡 PARTIAL"
            color = (0, 165, 255)
        else:
            status = "🔴 NOT FOCUSED"
            color = (0, 0, 255)
        
        # Large lock-in score display
        lock_panel_x = width - 330
        lock_panel_y = height - 140
        
        cv2.rectangle(frame, (lock_panel_x, lock_panel_y), (width - 10, height - 10), color, -1)
        cv2.rectangle(frame, (lock_panel_x, lock_panel_y), (width - 10, height - 10), (255, 255, 255), 3)
        
        cv2.putText(frame, "LOCK-IN SCORE", (lock_panel_x + 10, lock_panel_y + 25),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        
        score_text = f"{lock_in_score:.3f}"
        cv2.putText(frame, score_text, (lock_panel_x + 20, lock_panel_y + 70),
                   cv2.FONT_HERSHEY_SIMPLEX, 2.5, (255, 255, 255), 3)
        
        cv2.putText(frame, status, (lock_panel_x + 20, lock_panel_y + 110),
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
        
        # ============================================================
        # FORMULA & FPS (Top-center)
        # ============================================================
        font = cv2.FONT_HERSHEY_SIMPLEX
        formula_text = f"Score = Context({context_mult:.2f}) × Focus({focus_mult:.2f}) × (1-Fatigue({fatigue_score:.2f}))"
        cv2.putText(frame, formula_text, (10, height - 10),
                   font, 0.6, (255, 255, 255), 1)
        
        fps_text = f"FPS: {avg_fps:.1f} | Frame: {self.frame_count}"
        cv2.putText(frame, fps_text, (width - 250, height - 10),
                   font, 0.6, (255, 255, 255), 1)
        
        return frame
    
    def run_display_loop(self):
        """Display loop with overlay (runs in main thread)."""
        print("\n[DISPLAY] Opening overlay window...")
        print("[DISPLAY] Close the window or press 'q' to exit\n")
        
        cv2.namedWindow("Three-Gate Debug Overlay", cv2.WINDOW_AUTOSIZE)
        
        while self.running:
            # Create a blank frame for overlay
            frame = np.zeros((720, 1280, 3), dtype=np.uint8)
            frame = self.draw_overlay(frame)
            
            # Display
            try:
                cv2.imshow("Three-Gate Debug Overlay", frame)
            except Exception as e:
                print(f"[DISPLAY] Display error: {e}")
            
            # Handle key press with very short timeout to keep UI responsive
            key = cv2.waitKey(50) & 0xFF
            if key == ord('q') or key == 27:  # 'q' or ESC
                self.running = False
                break
        
        cv2.destroyAllWindows()
        print("\n[DISPLAY] Window closed")
    
    async def run_async(self):
        """Run WebSocket listener in background."""
        await self.websocket_listener()
    
    def start(self):
        """Start the tester."""
        print("\n" + "=" * 80)
        print("THREE-GATE DEBUG OVERLAY TESTER")
        print("=" * 80)
        print("\n📋 Instructions:")
        print("  1. Make sure the daemon is running: python -m fatigue_detection.app")
        print("  2. Sit in front of the camera")
        print("  3. Watch the overlay update in real-time")
        print("  4. Try these tests:")
        print("     - Switch between VSCode, Chrome, and Steam → Watch Gate 1 change")
        print("     - Look at screen, then look away → Watch Gate 2 change")
        print("     - Blink rapidly, yawn, or rest → Watch Gate 3 change")
        print("\n" + "=" * 80 + "\n")
        
        # Start WebSocket listener in background thread
        ws_thread = threading.Thread(target=lambda: asyncio.run(self.run_async()), daemon=True)
        ws_thread.start()
        
        # Give WebSocket time to connect
        import time
        time.sleep(2)
        
        # Run display loop in main thread
        try:
            self.run_display_loop()
        except KeyboardInterrupt:
            print("\n[INFO] Interrupted by user")
        finally:
            self.running = False
            ws_thread.join(timeout=1)
            print("\n✅ Test complete!")


if __name__ == "__main__":
    tester = DebugOverlayTester()
    tester.start()
