# Memory Allocation Fix

## Issue
The system was running out of memory trying to allocate 2.64 MiB for frames at 1280x720 resolution.

## Fixes Applied

1. **Reduced Camera Resolution** (in `app.py`):
   - Changed from 1280x720 to 640x480
   - Reduces memory per frame from ~2.64 MB to ~0.9 MB (about 66% reduction)

2. **Reduced Frame Processing Frequency**:
   - Changed from processing every 2nd frame to every 4th frame
   - Reduces CPU and memory usage

3. **Better Error Handling**:
   - Added checks for None/empty frames
   - Added MemoryError exception handling for frame copies

## If Memory Issues Persist

If you still see memory errors, you can:

1. **Further reduce resolution** (in `app.py` line ~80):
   ```python
   camera.set(cv2.CAP_PROP_FRAME_WIDTH, 320)
   camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 240)
   ```

2. **Disable camera display window** (set `show_camera_window = False`)

3. **Process frames even less frequently** (change `frame_skip % 4` to `frame_skip % 8`)

4. **Check system memory** - ensure you have enough RAM available

## Current Settings

- Resolution: 640x480 (reduced from 1280x720)
- Frame processing: Every 4th frame
- Buffer size: 1 frame (minimal buffering)

These settings should resolve the memory allocation errors while maintaining good detection performance.
