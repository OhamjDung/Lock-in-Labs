# Active Detectors Implementation

This document describes the implementation of the "Active Detectors" (Vibe Check) system, which includes the Psychomotor Vigilance Task (PVT) and Mouse Dynamics tracking.

## Overview

The Active Detectors system adds two complementary detection methods to validate and enhance camera-based fatigue detection:

1. **Psychomotor Vigilance Task (PVT)** - Reaction time test triggered at 70% fatigue
2. **Mouse Dynamics Tracking** - Mouse entropy analysis for fidgeting/burnout detection

## 1. Psychomotor Vigilance Task (PVT)

### Trigger
- Activates when fatigue score reaches **70% (0.7)** threshold
- 10-second cooldown between challenges
- Random delay of 1-5 seconds before shape appears

### Implementation
- **Module**: `pvt_challenge.py`
- **Integration**: `app.py` WebSocket handler
- **Frontend Flow**:
  1. Server sends `pvt_challenge` message with `delay_ms`
  2. Frontend waits `delay_ms`, then displays shape
  3. Frontend tracks time from shape appearance to Spacebar press
  4. Frontend sends `pvt_response` with `reaction_time_ms`
  5. Server interprets and sends `pvt_result` back

### Response Interpretation
- **< 250ms**: Alert (false alarm - camera was wrong, reset fatigue score)
- **250-500ms**: Normal reaction time
- **500-1000ms**: Impaired (confirm fatigue, suggest break)
- **> 1000ms or missed**: Severely impaired / Microsleep (force break)

### WebSocket Messages

**Challenge Sent:**
```json
{
  "type": "pvt_challenge",
  "delay_ms": 3241,
  "triggered_by_fatigue_score": 0.75,
  "message": "Reaction test: Press SPACEBAR when shape appears"
}
```

**Response Received:**
```json
{
  "type": "pvt_response",
  "reaction_time_ms": 420
}
```

**Result Sent:**
```json
{
  "type": "pvt_result",
  "reaction_time_ms": 420,
  "interpretation": "normal",
  "status": "normal",
  "message": "Normal reaction time"
}
```

## 2. Mouse Dynamics (Entropy Tracking)

### Concept
Tracks mouse movements to detect behavioral patterns:
- **Focused**: Smooth, linear paths (low entropy)
- **Fidgeting**: Circling cursor, random movements (medium entropy)
- **Burnout**: Aggressive movements, erratic velocity (high entropy)

### Implementation
- **Module**: `mouse_entropy.py`
- **Thread**: Runs in background using `pynput` library
- **Metrics**: Calculated continuously in sliding window (100 samples)

### Entropy Metrics

1. **Linear Entropy** (40% weight)
   - Measures path efficiency: straight-line distance / actual path distance
   - Low = straight lines (focused)
   - High = circular/random paths (fidgeting)

2. **Velocity Entropy** (30% weight)
   - Coefficient of variation in movement speed
   - Low = consistent speed (focused)
   - High = erratic speed changes (burnout)

3. **Direction Entropy** (30% weight)
   - Circular variance of movement directions
   - Low = consistent direction (focused)
   - High = random directions (fidgeting)

### Overall Entropy
Weighted combination of all three metrics (0.0 - 1.0):
- **< 0.3**: Focused state
- **0.3 - 0.6**: Fidgeting state
- **0.6 - 0.85**: Burnout state
- **> 0.85**: Idle/random state

### Metrics in WebSocket Output
Mouse metrics are automatically included in the metrics stream:

```json
{
  "type": "metrics",
  "timestamp": 1234567890,
  "data": {
    "fatigue_score": 0.65,
    "mouse_entropy": 0.42,
    "mouse_state": "fidgeting",
    "mouse_linear_entropy": 0.38,
    "mouse_velocity_entropy": 0.45,
    "mouse_direction_entropy": 0.43,
    ...
  }
}
```

## Setup

### Dependencies
Add to `requirements.txt`:
```
pynput>=1.7.6
```

Install:
```bash
pip install pynput
```

### Startup
The mouse tracker automatically starts when the FastAPI server starts (via lifespan handler). No manual initialization needed.

## Usage

### WebSocket Connection
Connect to `ws://localhost:8000/ws/fatigue-detect`

### Handling PVT Challenges (Frontend)
```javascript
websocket.onmessage = (event) => {
  const message = JSON.parse(event.data);
  
  if (message.type === 'pvt_challenge') {
    // Wait delay_ms, then show shape
    setTimeout(() => {
      showPVTShape();
      const startTime = Date.now();
      
      // Listen for spacebar
      const handler = (e) => {
        if (e.code === 'Space') {
          const reactionTime = Date.now() - startTime;
          websocket.send(JSON.stringify({
            type: 'pvt_response',
            reaction_time_ms: reactionTime
          }));
          removePVTShape();
          document.removeEventListener('keydown', handler);
        }
      };
      document.addEventListener('keydown', handler);
    }, message.delay_ms);
  }
  
  if (message.type === 'pvt_result') {
    // Handle result
    console.log(message.interpretation); // "alert", "normal", "impaired", "severely_impaired"
  }
  
  if (message.type === 'metrics') {
    // Metrics include mouse_entropy, mouse_state, etc.
    const mouseState = message.data.mouse_state;
    const mouseEntropy = message.data.mouse_entropy;
  }
};
```

## Integration Notes

- Mouse tracking runs in a separate thread (non-blocking)
- PVT challenges are tracked per WebSocket connection
- Mouse metrics are included in every metrics update
- PVT results can be used to adjust fatigue scores (currently logged, can be extended to modify C++ engine state)
- All metrics are thread-safe using locks

## Future Enhancements

1. **Fatigue Score Adjustment**: Integrate PVT results to directly modify fatigue scores in the C++ engine
2. **Mouse-Fatigue Correlation**: Use mouse entropy as input to fatigue score calculation
3. **Adaptive Thresholds**: Adjust PVT trigger threshold based on user history
4. **Advanced Mouse Patterns**: Detect specific patterns (text selection loops, rapid clicking, etc.)
