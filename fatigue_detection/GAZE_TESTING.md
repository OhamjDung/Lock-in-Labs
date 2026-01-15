# Gaze Detection Testing Guide

## How to Test Gaze Detection

The gaze detection system tracks where you're looking by monitoring head position. Here's how to test it:

### 1. **View Gaze Values on Screen**
When running the fatigue detection app, you'll see:
- **Gaze: X=0.00, Y=0.00** - This shows your current gaze direction
- **Gaze Stability: 0.00** - This shows how stable your gaze is (0.0 = very unstable, 1.0 = very stable)

### 2. **Test Horizontal Gaze (Left/Right)**
- **Look LEFT**: The `X` value should become **negative** (e.g., X=-0.20)
- **Look RIGHT**: The `X` value should become **positive** (e.g., X=0.20)
- **Look CENTER**: The `X` value should be close to **0.00**

### 3. **Test Vertical Gaze (Up/Down)**
- **Look UP**: The `Y` value should become **negative** (e.g., Y=-0.15)
- **Look DOWN**: The `Y` value should become **positive** (e.g., Y=0.15)
- **Look CENTER**: The `Y` value should be close to **0.00**

### 4. **Test Gaze Stability**
- **Keep your head STILL**: Gaze Stability should increase toward **1.0**
- **Move your head around**: Gaze Stability should decrease toward **0.0**
- **Look at one spot for 5+ seconds**: Stability should be **> 0.7**

### 5. **What the Values Mean**
- **X Range**: -0.5 (far left) to +0.5 (far right)
- **Y Range**: -0.5 (far up) to +0.5 (far down)
- **Stability Range**: 0.0 (very unstable) to 1.0 (very stable)

### 6. **Troubleshooting**
- If values don't change when you move your head:
  - Make sure your face is detected (check "Face Detected: True")
  - Ensure good lighting
  - Try moving more slowly
  
- If stability is always low:
  - This is normal if you're moving your head frequently
  - Try keeping your head still for a few seconds to see stability increase

### 7. **Integration with Fatigue Detection**
Gaze stability is used in the fatigue score calculation:
- **High stability** (0.7+) = Good focus, lower fatigue
- **Low stability** (0.4-) = Distracted/unstable, higher fatigue
