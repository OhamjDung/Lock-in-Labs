# Three-Gate System Testing Guide

## Quick Start

### Step 1: Start the Daemon
Open a terminal and run:
```bash
cd "d:\Noobcept\Lock In Labs"
python -m fatigue_detection.app
```

**Wait for these messages:**
```
[OK] MediaPipe vision system initialized
[OK] Window tracker initialized (Gate 1)
[OK] Screen geometry initialized (Gate 2)
INFO:     Uvicorn running on http://127.0.0.1:8000
[INFO] Camera display window opened. Press 'q' in window to close.
```

**IMPORTANT:** Keep this terminal open! The daemon must keep running.

---

### Step 2: Run the Debug Overlay (New Terminal)
Open a **second** terminal and run:
```bash
cd "d:\Noobcept\Lock In Labs"
python fatigue_detection/test_debug_overlay.py
```

You should see:
```
[WS] Connecting to ws://127.0.0.1:8000/ws/fatigue-detect...
[WS] ✅ Connected to daemon!
[WS] Received 30 messages...
[WS] Received 60 messages...
[DISPLAY] Opening overlay window...
```

---

## What You Should See

### Debug Overlay Window
A 1280x720 window with 4 panels:

**Top-Left: GATE 1 (Context)**
- Shows active window title
- Context multiplier (0.0 - 1.0)
- Status: 🔓 PRODUCTIVE / ⚠️ AMBIGUOUS / 🔒 DISTRACTED

**Top-Right: GATE 2 (Focus)**
- Gaze position (x, y)
- Looking at screen: ✓ YES / ✗ NO
- Focus multiplier (0.0 or 1.0)

**Bottom-Left: GATE 3 (Fatigue)**
- Fatigue score (0.0 - 1.0)
- Fatigue multiplier (1.0 - 0.0)
- Blink rate (bpm)
- Status: 😴 ALERT / ⚠️ MODERATE / 🚨 SEVERE

**Bottom-Right: LOCK-IN SCORE**
- Large score display (0.000 - 1.000)
- Overall status: 🟢 LOCKED IN / 🟡 PARTIAL / 🔴 NOT FOCUSED

---

## Testing Scenarios

### Test 1: Context Gate
**Goal:** Verify active window detection

1. Keep overlay visible
2. Switch windows:
   - **VSCode** → Should show multiplier = 1.0 (green)
   - **Chrome (localhost/GitHub)** → Should show 1.0 (green)
   - **Chrome (YouTube)** → Should show 0.0 (red)
   - **Steam** → Should show 0.0 (red)
3. Watch Gate 1 panel update

**Expected:** Context multiplier changes based on window

---

### Test 2: Focus Gate
**Goal:** Verify gaze tracking

1. Sit in front of camera
2. Look directly at screen → Gate 2 should show "✓ YES" (green)
3. Look away (left/right/down) → Gate 2 should show "✗ NO" (red)
4. Look back → Should return to "✓ YES"

**Expected:** Focus multiplier toggles between 1.0 and 0.0

---

### Test 3: Fatigue Gate
**Goal:** Verify fatigue detection

1. Sit normally → Fatigue multiplier should be high (~0.8-1.0, green)
2. Blink rapidly for 10 seconds → Should decrease slightly
3. Yawn (open mouth wide) → Should decrease more
4. Rest with eyes closed for 5 seconds → Should drop significantly (red)

**Expected:** Fatigue multiplier decreases with tiredness signs

---

### Test 4: Combined Lock-In Score
**Goal:** Verify multiplication formula

**Test Case 1:** Full lock-in
- Open VSCode
- Look at screen
- Stay alert
- **Expected:** Lock-in score ≈ 0.8-1.0 (🟢 green)

**Test Case 2:** Partial productivity
- Open Chrome (YouTube)
- Look at screen
- Stay alert
- **Expected:** Lock-in score ≈ 0.0 (🔴 red, context failed)

**Test Case 3:** Looking away
- Open VSCode
- Look away from screen
- **Expected:** Lock-in score = 0.0 (🔴 red, focus failed)

**Test Case 4:** Fatigued
- Open VSCode
- Look at screen
- Close eyes / yawn repeatedly
- **Expected:** Lock-in score drops (🟡 yellow → 🔴 red)

---

## Troubleshooting

### "Connection error: no close frame received or sent"
**Problem:** Daemon is not sending data

**Solutions:**
1. Check if face is detected:
   - Look at the camera window (from daemon)
   - Make sure your face is visible and well-lit
2. Restart daemon:
   ```bash
   # Kill daemon (Ctrl+C in daemon terminal)
   # Restart it
   python -m fatigue_detection.app
   ```

### "No data received in 5 seconds"
**Problem:** Camera not processing frames

**Solutions:**
1. Check camera window shows your face
2. Verify good lighting
3. Move closer to camera

### Overlay shows "Waiting..."
**Problem:** No metrics received yet

**Solutions:**
1. Wait 5-10 seconds for initialization
2. Make sure daemon is running (check terminal 1)
3. Restart overlay if still waiting after 30 seconds

### Lock-in score always 0.0
**Possible causes:**
- No face detected (check camera window)
- Looking away from screen
- Distracting app open (Steam, YouTube, etc.)

---

## Expected Output Example

When working correctly, you should see console output like:
```
[WS] ✅ Connected to daemon!
[WS] Received 30 messages...
[WS] Received 60 messages...
[WS] Received 90 messages...
[DISPLAY] Opening overlay window...
```

And the overlay should update smoothly (~20-30 FPS).

---

## Keyboard Controls

- **'q' or ESC** in overlay window = Close overlay
- **'q' or ESC** in camera window = Close daemon

---

## Performance Notes

- **FPS:** Should be 20-30 FPS (shown at bottom-right)
- **Latency:** Gate updates should be < 100ms
- **CPU:** ~10-20% for daemon, ~5% for overlay

---

## Known Issues

1. **First connection slow:** Initial WebSocket connection may take 2-3 seconds
2. **Browser detection delay:** Window tracker polls every 2 seconds, so window changes have slight delay
3. **Gaze calibration:** If you have multiple monitors, gaze bounds may need adjustment

---

## Next Steps

After successful testing:
1. Integrate with frontend (React WebSocket client)
2. Add notification system (alerts for distractions)
3. Add calibration wizard (multi-monitor support)
4. Train personalized lock-in model (collect user ratings)

