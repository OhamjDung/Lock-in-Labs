# Three-Gate Lock-In Detection System

## Overview

The **Three-Gate System** is a multiplicative scoring architecture that combines three independent signals to determine whether a user is truly "locked in" to productive work:

```
Lock-In Score = Context × Focus × (1 - Fatigue)
```

Each gate acts as an **independent veto** - if any gate closes (multiplier = 0), the entire lock-in score drops to zero. This prevents false positives from traditional fatigue-only systems.

---

## Architecture

### Gate 1: Context Gate (Active Window Detection)
**Purpose:** Is the user in a productive context?

**Implementation:** `window_tracker.py`
- Polls active window title every 2 seconds using Windows API (`win32gui`)
- Matches against application whitelist
- Returns context multiplier (0.0 - 1.0)

**Multiplier Values:**
- **1.0** = Highly productive (IDEs, terminals, design tools)
  - Examples: VSCode, PyCharm, Visual Studio, Terminal, Figma
- **0.7** = Work-adjacent (communication tools)
  - Examples: Slack, Teams, Discord, Zoom
- **Browsers (Chrome, Firefox, Edge)** = **Keyword Scanning (Work-First Priority):**
  - **1.0** if title contains ANY work keyword (localhost, GitHub, Stack Overflow, docs, API, developers)
    - "Twitter API Docs" → **1.0** ("docs" found first)
    - "Facebook for Developers" → **1.0** ("developers" keyword)
    - **Principle: Benefit of the doubt - user gets credit if ANY work indicator exists**
  - **0.0** if title contains ONLY entertainment keywords (YouTube, Netflix, Reddit, TikTok)
  - **0.5** if truly ambiguous (no matching keywords)
  - **Priority order:** WORK keywords checked first, ENTERTAINMENT keywords checked second
- **0.0** = Distracting (games, streaming apps)
  - Examples: Steam, League of Legends, Epic Games

## Key Design Decision: "Benefit of the Doubt"

**The Clash:** When a browser title contains BOTH work AND entertainment keywords, which wins?

Example: "Twitter API Docs - Google Chrome"
- Contains "Twitter" (entertainment keyword) 
- Contains "Docs" (work keyword)

**Resolution:** **WORK keywords are checked FIRST.** The system gives users the benefit of the doubt:
- If ANY work indicator is present, assume productivity (multiplier = 1.0)
- Only if NO work keywords are found, check for entertainment
- Philosophy: A developer reading API docs on Twitter's platform should get FULL credit, not penalized

**Examples:**
```
"Twitter API Docs" → 1.0 (docs keyword found first)
"Facebook for Developers" → 1.0 (developers keyword)
"Reddit - Learning Python" → 1.0 (docs-like learning context)
"Reddit - r/funny" → 0.0 (entertainment keyword, no work indicator)
"YouTube - JavaScript Tutorial" → 0.5 (ambiguous - could add 'tutorial' as work keyword)
```

---


```python
from fatigue_detection.window_tracker import WindowTracker

tracker = WindowTracker(poll_interval=2.0)
title, multiplier = tracker.get_active_window()

# "Visual Studio Code - main.py" → 1.0 (IDE)
# "Chrome - localhost:3000" → 1.0 (work keyword)
# "Chrome - Stack Overflow" → 1.0 (work keyword)
# "Firefox - YouTube" → 0.0 (entertainment keyword)
# "Edge - New Tab" → 0.5 (ambiguous, no keywords)
# "Steam" → 0.0 (game launcher)
```

---

### Gate 2: Focus Gate (Screen Attention Detection)
**Purpose:** Is the user looking at the screen?

**Implementation:** `screen_geometry.py`
- Checks if gaze coordinates fall within screen boundaries
- Combines gaze direction + phone detection
- Returns focus multiplier (0.0 or 1.0)

**Logic:**
```
Focus = 1.0 IF (looking_at_screen AND NOT phone_detected)
Focus = 0.0 OTHERWISE
```

**Gaze Coordinate System:**
- MediaPipe gaze: `[-0.5, 0.5]` normalized (0,0 = center of face)
- Screen bounds: `±(0.5 + tolerance)` where tolerance = 15% by default
- Examples:
  - `(0.0, 0.0)` = Looking straight (center) → **ON SCREEN**
  - `(0.3, 0.2)` = Looking right-down → **ON SCREEN**
  - `(0.6, 0.0)` = Looking far right → **OFF SCREEN**

**Multi-Monitor Support:**
- Uses `screeninfo` library to detect monitor configuration
- Automatically finds primary monitor
- Can calibrate bounds based on user's specific setup

**Example:**
```python
from fatigue_detection.screen_geometry import ScreenGeometry

screen = ScreenGeometry(tolerance=0.15)
looking = screen.is_looking_at_screen(gaze_x=0.0, gaze_y=0.0)  # True
region = screen.get_gaze_region(gaze_x=-0.7, gaze_y=0.0)  # "left"
focus = screen.get_focus_multiplier(0.0, 0.0, phone_detected=False)  # 1.0
```

---

### Gate 3: Fatigue Gate (Energy Level)
**Purpose:** Is the user alert enough to maintain productivity?

**Implementation:** C++ fatigue detection engine
- Combines blink rate, PERCLOS, gaze stability, yawns, fidgeting
- Z-score fusion algorithm (personalized per user)
- Fatigue multiplier = `1.0 - fatigue_score`

**Multiplier Calculation:**
```
Fatigue Multiplier = 1.0 - fatigue_score

Examples:
  fatigue_score = 0.2 (20% fatigued) → multiplier = 0.8
  fatigue_score = 0.5 (50% fatigued) → multiplier = 0.5
  fatigue_score = 0.9 (90% fatigued) → multiplier = 0.1
```

**Key Metrics:**
- **Blink Rate:** Blinks/minute (elevated = fatigue)
- **PERCLOS:** Percentage of eye closure (higher = drowsiness)
- **Gaze Stability:** Eye jitter (lower = unfocused)
- **Yawn Count:** Recent yawns (more = tired)
- **Head Movement:** Fidgeting, neck cracks (more = restlessness)

---

## Integration Points

### 1. FastAPI Daemon (`app.py`)
**WebSocket Endpoint:** `/ws/fatigue-detect`

**Processing Loop (every frame):**
```python
# 1. Process frame with MediaPipe
vision_results = vision_system.process(frame)

# 2. Gate 1: Context (poll every 2s, cached)
window_title, context_mult = window_tracker.get_active_window()

# 3. Gate 2: Focus (every frame)
looking = screen_geometry.is_looking_at_screen(gaze_x, gaze_y)
focus_mult = screen_geometry.get_focus_multiplier(gaze_x, gaze_y, phone_detected)

# 4. Gate 3: Fatigue (C++ engine)
metrics = engine.update_metrics(ear, mar, gaze_x, gaze_y, timestamp_ms, ...)
fatigue_mult = 1.0 - metrics["fatigue_score"]

# 5. Combine gates
lock_in_score = context_mult * focus_mult * fatigue_mult

# 6. Broadcast to frontend
await websocket.send_json({
    "type": "metrics",
    "data": {
        "active_window": window_title,
        "context_multiplier": context_mult,
        "looking_at_screen": looking,
        "focus_multiplier": focus_mult,
        "fatigue_multiplier": fatigue_mult,
        "lock_in_score": lock_in_score,
        ...
    }
})
```

### 2. Display Loop (Camera Window)
- Same logic as WebSocket loop
- Updates `latest_metrics` for thread-safe sharing
- Shows gate status in overlay

---

## Dependencies

```bash
pip install pywin32>=306       # Windows API (active window)
pip install screeninfo>=0.8    # Multi-monitor detection
```

**Already included:**
- `opencv-python` (camera, vision processing)
- `mediapipe` (face tracking, gaze estimation)

---

## Testing

### Manual Test (Camera Window)
```bash
cd "d:\Noobcept\Lock In Labs"
python -m fatigue_detection.app
```

**Test Scenarios:**
1. **Context Test:** Switch apps (VSCode → Chrome → Steam), watch `context_multiplier`
2. **Focus Test:** Look at screen, then look away (left/right/down), watch `focus_multiplier`
3. **Fatigue Test:** Blink rapidly, yawn, shake head, watch `fatigue_multiplier`
4. **Combined Test:** Open Steam while looking away while tired → `lock_in_score = 0.0`

### WebSocket Test Script
```bash
python fatigue_detection/test_three_gates.py
```

**Output Example:**
```
 Frame | Window                         |  Ctx |  Foc |  Fat | Lock-In | Status
--------------------------------------------------------------------------------
     1 | Visual Studio Code - main.py   |  1.0 |  1.0 |  0.8 |   0.800 | 👁️  🟢 LOCKED IN
    45 | Chrome - YouTube               |  0.5 |  1.0 |  0.8 |   0.400 | 👁️  🟡 PARTIAL
    89 | Steam                          |  0.0 |  0.0 |  0.8 |   0.000 |    🔴 NOT FOCUSED
   134 | Visual Studio Code - main.py   |  1.0 |  0.0 |  0.8 |   0.000 |    🔴 NOT FOCUSED (looking away)
```

---

## Notification Hierarchy (TODO)

**Three-tier alert system:**

### Tier 1: Context Warning (Gate 1 closed)
**Trigger:** `context_multiplier == 0.0` for >30 seconds
**Message:** "Distraction detected: You're on {app_name}. Return to work?"
**Severity:** LOW

### Tier 2: Focus Warning (Gate 2 closed)
**Trigger:** `focus_multiplier == 0.0` for >60 seconds
**Message:** "You've been looking away from the screen. Take a break?"
**Severity:** MEDIUM

### Tier 3: Fatigue Alert (Gate 3 closing)
**Trigger:** `fatigue_multiplier < 0.3` (fatigue > 70%)
**Message:** "High fatigue detected. Time for a break!"
**Severity:** HIGH

**Future Enhancement:** PVT challenges when fatigue is borderline (50-70%) to objectively measure alertness.

---

## Calibration & Training (Future)

### Phase 1: User Rating Collection
- Every 15 minutes, prompt: "How locked in are you? (1-10)"
- Collect tuples: `(context, focus, fatigue, user_rating)`
- Store in `data/user_ratings_{user_id}.json`

### Phase 2: Regression Training
- Train regression model: `lock_in_score = f(context, focus, fatigue)`
- Learn personalized weights (e.g., some users care more about context than fatigue)
- Replace simple multiplication with learned function

### Phase 3: Active Learning
- When model is uncertain, ask user for rating
- Continuously improve over time

---

## Performance Considerations

### Overhead per Frame (~30 FPS)
- **Gate 1 (Context):** ~0ms (cached, polls every 2s)
- **Gate 2 (Focus):** ~0.1ms (simple boundary check)
- **Gate 3 (Fatigue):** Already integrated in C++ engine (~5ms)
- **Total Added Latency:** <1ms per frame

### Memory Footprint
- **WindowTracker:** <1KB (cached window title)
- **ScreenGeometry:** <10KB (monitor info)
- **Total Added Memory:** <50KB

**Conclusion:** Negligible impact on performance.

---

## File Structure

```
fatigue_detection/
├── app.py                      # Main daemon (WebSocket server)
├── window_tracker.py           # Gate 1: Context detection
├── screen_geometry.py          # Gate 2: Focus detection
├── engine.py                   # Gate 3: Fatigue detection (C++ wrapper)
├── test_three_gates.py         # Integration test script
├── cpp/
│   ├── include/detector.h      # StateVector with gate fields
│   ├── src/detector.cpp        # Gate 3 implementation
│   └── src/profile_manager.cpp # Lock-in score calculation (C++)
└── ...
```

---

## Usage in Production

### Backend (Python)
```python
# Already integrated in app.py
# Just run the daemon:
python -m fatigue_detection.app
```

### Frontend (React/JavaScript)
```javascript
const ws = new WebSocket('ws://127.0.0.1:8000/ws/fatigue-detect');

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'metrics') {
        const {
            lock_in_score,
            context_multiplier,
            focus_multiplier,
            fatigue_multiplier,
            active_window,
            looking_at_screen
        } = msg.data;
        
        // Update UI
        document.getElementById('lock-in-bar').style.width = `${lock_in_score * 100}%`;
        document.getElementById('active-app').textContent = active_window;
        
        // Show warnings
        if (context_multiplier === 0.0) {
            showNotification('Distraction detected!');
        }
        if (!looking_at_screen) {
            showNotification('Not looking at screen');
        }
    }
};
```

---

## Known Limitations & Future Work

### Critical Design Note: Browser Keyword Scanning
**Problem Solved:** The original design had a "Browser Penalty" - ALL browsers received 0.5 multiplier, which would permanently cap web developers/researchers at 50% lock-in.

**Solution Implemented:** Browsers now use **title keyword scanning**:
- Work keywords (localhost, GitHub, Stack Overflow, docs) → **1.0** (full productivity)
- Entertainment keywords (YouTube, Netflix, Reddit) → **0.0** (distraction)
- Unknown/ambiguous → **0.5** (neutral)

This ensures web developers working in Chrome get full credit while still catching entertainment distractions.

### Current Limitations
1. **Phone Detection:** Not yet integrated (requires separate WebSocket)
2. **Calibration:** Lock-in formula is hardcoded (not personalized)
3. **Notifications:** Tier system not implemented
4. **Multi-tasking:** Can't detect if user switches monitors
5. **Multi-Monitor Gaze:** Calibration assumes single centered monitor (needs offset calibration for side monitors)

### Planned Improvements
1. **Phone Detector Integration:** Connect to `/ws/phone-detect` endpoint
2. **User Training:** Collect ratings, train personalized model
3. **Multi-Monitor Support:** Track which monitor user is looking at
4. **Keyboard/Mouse Activity:** Add Gate 4 (input activity tracking)
5. **Application Context Depth:** Distinguish work tabs from distraction tabs in browsers

---

## References

- **Window Tracking:** Windows API (`win32gui.GetForegroundWindow()`)
- **Screen Geometry:** `screeninfo` library for multi-monitor bounds
- **Fatigue Detection:** MediaPipe Face Mesh + custom C++ algorithms
- **Lock-In Formula:** Inspired by AND-gate logic in digital circuits (all gates must be open)

---

## Contributors

- **Initial Implementation:** Lock In Labs Team
- **Three-Gate Architecture:** Design session (fatigue + context + focus)
- **Testing:** Ongoing user validation

---

## License

Proprietary - Lock In Labs
