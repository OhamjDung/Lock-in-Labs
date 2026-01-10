#!/usr/bin/env python
"""
Simple test script to connect to fatigue detection WebSocket and display metrics.
Run this while the daemon (app.py) is running.
"""

import asyncio
import json
import websockets
from datetime import datetime


async def test_websocket():
    """Connect to WebSocket and display incoming metrics."""
    uri = "ws://127.0.0.1:8000/ws/fatigue-detect"
    
    print("=" * 60)
    print("Fatigue Detection WebSocket Test")
    print("=" * 60)
    print(f"Connecting to: {uri}")
    print("Make sure app.py is running in another terminal!")
    print("Press Ctrl+C to stop\n")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("✅ Connected to WebSocket!\n")
            print("Waiting for metrics... (make sure you're in front of the camera)\n")
            print("-" * 60)
            
            frame_count = 0
            last_pvt_time = None
            
            while True:
                try:
                    # Receive message (with timeout to allow keyboard interrupt)
                    message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                    data = json.loads(message)
                    frame_count += 1
                    
                    # Handle different message types
                    if data.get("type") == "metrics":
                        metrics = data.get("data", {})
                        timestamp = data.get("timestamp", 0)
                        
                        # Format timestamp
                        dt = datetime.fromtimestamp(timestamp / 1000)
                        time_str = dt.strftime("%H:%M:%S.%f")[:-3]
                        
                        # Extract key metrics
                        fatigue_score = metrics.get("fatigue_score", 0.0)
                        blink_rate = metrics.get("blink_rate", 0.0)
                        yawn_count = metrics.get("yawn_count", 0)
                        fidget_score = metrics.get("fidget_score", 0.0)
                        face_detected = metrics.get("face_detected", False)
                        
                        # Display metrics (clear line behavior)
                        print(f"\r[{time_str}] Frame #{frame_count} | "
                              f"Face: {'✓' if face_detected else '✗'} | "
                              f"Fatigue: {fatigue_score:.2f} | "
                              f"Blink: {blink_rate:.1f}/min | "
                              f"Yawns: {yawn_count} | "
                              f"Fidget: {fidget_score:.2f}", end="", flush=True)
                        
                        # Show warning if fatigue score is high
                        if fatigue_score >= 0.7:
                            print(f"\n⚠️  HIGH FATIGUE ALERT! (Score: {fatigue_score:.2f})")
                    
                    elif data.get("type") == "pvt_challenge":
                        delay_ms = data.get("delay_ms", 0)
                        fatigue_score = data.get("triggered_by_fatigue_score", 0.0)
                        print(f"\n\n🎯 PVT CHALLENGE TRIGGERED!")
                        print(f"   Fatigue score: {fatigue_score:.2f}")
                        print(f"   Challenge will appear in {delay_ms/1000:.1f} seconds")
                        print(f"   (Press spacebar when you see the prompt)\n")
                        last_pvt_time = datetime.now()
                    
                    elif data.get("type") == "error":
                        error_msg = data.get("message", "Unknown error")
                        print(f"\n❌ Error: {error_msg}")
                        break
                
                except asyncio.TimeoutError:
                    # Allow keyboard interrupt during timeout
                    continue
                
    except websockets.exceptions.ConnectionRefusedError:
        print("\n❌ Connection refused!")
        print("   Make sure app.py is running:")
        print("   python fatigue_detection/app.py")
    except KeyboardInterrupt:
        print("\n\n👋 Test stopped by user")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("Starting WebSocket test...\n")
    asyncio.run(test_websocket())
