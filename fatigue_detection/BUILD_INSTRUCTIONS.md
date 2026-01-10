# Build Instructions - Cursor IDE

Follow these steps in order. All commands run in Cursor's integrated terminal.

## Step 1: Install C++ Dependencies via MSYS2

You need to install OpenCV, Dlib, Eigen, and Pybind11. These are installed via MSYS2's package manager.

### Option A: Using MSYS2 Terminal (Recommended)

1. **Open MSYS2 UCRT64 terminal** (separate from Cursor):
   - Press `Win + R`, type: `C:\msys64\ucrt64.exe`
   - Or search "MSYS2 UCRT64" in Start menu

2. **In MSYS2 terminal, run:**
   ```bash
   # Update package database
   pacman -Syu
   
   # Install dependencies (this may take 10-20 minutes)
   pacman -S mingw-w64-ucrt-x86_64-opencv
   pacman -S mingw-w64-ucrt-x86_64-dlib
   pacman -S mingw-w64-ucrt-x86_64-eigen3
   pacman -S mingw-w64-ucrt-x86_64-pybind11
   ```

3. **Wait for installation to complete**, then close MSYS2 terminal.

### Option B: Check if Already Installed

In Cursor terminal (PowerShell), check if packages exist:
```powershell
Test-Path "C:\msys64\ucrt64\lib\cmake\opencv4"
Test-Path "C:\msys64\ucrt64\include\dlib"
Test-Path "C:\msys64\ucrt64\include\eigen3"
```

If all return `True`, dependencies are installed. If any return `False`, use Option A.

## Step 2: Download Dlib Landmark Model

In Cursor terminal (PowerShell):
```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection\models"

# Download the model file
Invoke-WebRequest -Uri "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2" -OutFile "shape_predictor_68_face_landmarks.dat.bz2"

# Extract (requires 7-Zip or use online extractor)
# If you have 7-Zip installed:
& "C:\Program Files\7-Zip\7z.exe" x shape_predictor_68_face_landmarks.dat.bz2

# Or download pre-extracted from: http://dlib.net/files/shape_predictor_68_face_landmarks.dat
```

## Step 3: Configure CMake

In Cursor terminal (PowerShell):
```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection\cpp\build"

# Clean any previous attempts
Remove-Item CMakeCache.txt -ErrorAction SilentlyContinue
Remove-Item CMakeFiles -Recurse -ErrorAction SilentlyContinue

# Configure with MinGW and set library paths
cmake .. -G "MinGW Makefiles" `
  -DCMAKE_C_COMPILER=gcc `
  -DCMAKE_CXX_COMPILER=g++ `
  -DOpenCV_DIR="C:\msys64\ucrt64\lib\cmake\opencv4" `
  -DDlib_DIR="C:\msys64\ucrt64\lib\cmake" `
  -DEigen3_DIR="C:\msys64\ucrt64\share\eigen3\cmake"
```

**Expected output:** Should see "Configuring done" and "Generating done" without errors.

## Step 4: Build the Module

In Cursor terminal (PowerShell):
```powershell
# Still in build directory
mingw32-make
```

**Expected output:** Should see compilation progress and end with "Built target lockin_core"

**Time:** This may take 5-15 minutes depending on your CPU.

## Step 5: Verify Build

In Cursor terminal (PowerShell):
```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection"

# Check if module was created
Get-ChildItem *.pyd, *.so -ErrorAction SilentlyContinue

# Test Python import
python -c "import lockin_core; print('Success! Module loaded.')"
```

**Expected:** Should see "Success! Module loaded." without errors.

## Step 6: Install Python Dependencies

In Cursor terminal (PowerShell):
```powershell
cd "D:\Noobcept\Lock In Labs"
pip install -r fatigue_detection\requirements.txt
```

## Step 7: Test the Daemon

In Cursor terminal (PowerShell):
```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection"
python app.py
```

**Expected:** Server starts on `http://127.0.0.1:8000` and camera opens.

## Troubleshooting

### CMake can't find OpenCV
- Verify path: `Test-Path "C:\msys64\ucrt64\lib\cmake\opencv4"`
- If False, install via MSYS2 (Step 1)
- Try different path: `C:\msys64\mingw64\lib\cmake\opencv4` (if using mingw64 instead of ucrt64)

### Build errors about missing headers
- Check include paths exist:
  ```powershell
  Test-Path "C:\msys64\ucrt64\include\opencv4"
  Test-Path "C:\msys64\ucrt64\include\dlib"
  Test-Path "C:\msys64\ucrt64\include\eigen3"
  ```

### Import error: "No module named lockin_core"
- Check module exists: `Get-ChildItem fatigue_detection\*.pyd`
- Ensure you're in the right directory
- Check Python architecture matches (64-bit)

### "mingw32-make: command not found"
- Use full path: `C:\msys64\ucrt64\bin\mingw32-make.exe`
- Or add to PATH: `$env:Path += ";C:\msys64\ucrt64\bin"`
