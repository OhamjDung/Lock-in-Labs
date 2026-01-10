# Face Detection Troubleshooting

## Changes Made

1. ✅ **Added model path initialization** - FaceEngine now tries multiple paths to find the landmark model
2. ✅ **Added visual feedback** - Camera window shows "FACE DETECTED" or "NO FACE" status
3. ✅ **Better error logging** - Shows which paths were tried for model loading
4. ✅ **Fixed working directory** - Python changes to fatigue_detection directory before initializing engine

## Model File Location

The model file should be at:
```
fatigue_detection/models/shape_predictor_68_face_landmarks.dat
```

If missing, download from:
http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2

Extract and place in `fatigue_detection/models/`

## To Test Face Detection

1. **Rebuild the C++ module** (if you just modified detector.cpp):
   ```powershell
   cd "D:\Noobcept\Lock In Labs\fatigue_detection\cpp\build"
   mingw32-make
   ```

2. **Run the server**:
   ```powershell
   cd "D:\Noobcept\Lock In Labs"
   python fatigue_detection/app.py
   ```

3. **Check the camera window**:
   - Should show your face
   - Green text "FACE DETECTED" in top-right = working
   - Red text "NO FACE" = not detecting

## Common Issues

### Model Not Loading
- Check console output for: `[FatigueEngine] Successfully loaded landmark model`
- If you see warnings, the model path is wrong
- Make sure `fatigue_detection/models/shape_predictor_68_face_landmarks.dat` exists

### Face Still Not Detecting
- **Lighting**: Make sure you're in a well-lit area
- **Distance**: Sit 1-3 feet from camera
- **Position**: Face camera directly (not at angle)
- **Camera**: Try different camera: `/api/fatigue/set-user/default_user?camera_index=1`

### Camera Window Not Showing
- Check if OpenCV can access camera: `python -c "import cv2; cap = cv2.VideoCapture(0); print('OK' if cap.isOpened() else 'FAILED'); cap.release()"`
- Make sure no other app is using the camera
