"""
Quick test for the three-gate system integration.
Run this to verify gate multipliers are working correctly.
"""

import asyncio
import json
import websockets
from datetime import datetime


async def test_three_gate_system():
    """Connect to fatigue detection daemon and monitor gate multipliers."""
    uri = "ws://127.0.0.1:8000/ws/fatigue-detect"
    
    print("=" * 80)
    print("THREE-GATE SYSTEM TEST")
    print("=" * 80)
    print(f"Connecting to: {uri}")
    print("\nMake sure the daemon (app.py) is running!")
    print("\nInstructions:")
    print("  1. Switch between different apps (VSCode, Chrome, Steam, etc.)")
    print("  2. Look at screen, then look away")
    print("  3. Watch how lock_in_score changes based on gates")
    print("\nPress Ctrl+C to stop\n")
    print("-" * 80)
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected!\n")
            
            frame_count = 0
            last_window = None
            last_looking = None
            
            # Column headers
            print(f"{'Frame':>6} | {'Window':30s} | {'Ctx':>4} | {'Foc':>4} | {'Fat':>4} | {'Lock-In':>7} | Status")
            print("-" * 80)
            
            while True:
                try:
                    # Receive metrics
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    
                    if data.get("type") != "metrics":
                        continue
                    
                    frame_count += 1
                    metrics = data.get("data", {})
                    
                    # Extract gate values
                    active_window = metrics.get("active_window", "Unknown")
                    context_mult = metrics.get("context_multiplier", 0.0)
                    looking = metrics.get("looking_at_screen", False)
                    focus_mult = metrics.get("focus_multiplier", 0.0)
                    fatigue_mult = metrics.get("fatigue_multiplier", 0.0)
                    lock_in_score = metrics.get("lock_in_score", 0.0)
                    face_detected = metrics.get("face_detected", False)
                    
                    # Only print when something changes or every 30 frames
                    changed = (
                        active_window != last_window or 
                        looking != last_looking or 
                        frame_count % 30 == 0
                    )
                    
                    if changed:
                        # Truncate window title
                        window_short = active_window[:28] if len(active_window) > 28 else active_window
                        
                        # Status indicator
                        if lock_in_score >= 0.7:
                            status = "🟢 LOCKED IN"
                        elif lock_in_score >= 0.3:
                            status = "🟡 PARTIAL"
                        else:
                            status = "🔴 NOT FOCUSED"
                        
                        # Face detection indicator
                        if not face_detected:
                            status = "⚫ NO FACE"
                        
                        # Looking indicator
                        looking_icon = "👁️ " if looking else "  "
                        
                        print(f"{frame_count:6d} | {window_short:30s} | {context_mult:4.1f} | {focus_mult:4.1f} | {fatigue_mult:4.1f} | {lock_in_score:7.3f} | {looking_icon}{status}")
                        
                        last_window = active_window
                        last_looking = looking
                
                except asyncio.TimeoutError:
                    continue
                
    except websockets.exceptions.ConnectionClosed:
        print("\n❌ Connection closed")
    except KeyboardInterrupt:
        print("\n\n[INFO] Stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    print("\nStarting test...\n")
    asyncio.run(test_three_gate_system())
