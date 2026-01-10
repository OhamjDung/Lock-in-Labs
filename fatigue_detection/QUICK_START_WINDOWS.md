# Quick Start - Windows PowerShell

## Step 1: Install CMake

**Manual Installation (Easiest):**
1. Open browser and go to: https://cmake.org/download/
2. Download "Windows x64 Installer" (cmake-x.x.x-windows-x86_64.msi)
3. Run installer
4. **Important:** Check "Add CMake to system PATH for all users" during installation
5. Restart PowerShell

**Verify installation:**
```powershell
cmake --version
```

## Step 2: Install Visual Studio Build Tools

You need a C++ compiler. Get Visual Studio Build Tools:
1. Download: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
2. Run installer
3. Select "Desktop development with C++"
4. Install

## Step 3: Install Python Dependencies

```powershell
cd "D:\Noobcept\Lock In Labs"
pip install -r fatigue_detection\requirements.txt
```

## Step 4: Install C++ Dependencies (Using vcpkg - Recommended)

```powershell
# Install vcpkg
git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat

# Install dependencies (this takes a while)
.\vcpkg\vcpkg install opencv:x64-windows
.\vcpkg\vcpkg install dlib:x64-windows
.\vcpkg\vcpkg install pybind11:x64-windows
.\vcpkg\vcpkg install eigen3:x64-windows

# Integrate with Visual Studio
.\vcpkg\vcpkg integrate install
```

## Step 5: Download Dlib Landmark Model

```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection\models"
Invoke-WebRequest -Uri "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2" -OutFile "shape_predictor_68_face_landmarks.dat.bz2"
```

Then extract the .bz2 file (you may need 7-Zip or use an online extractor):
- 7-Zip: Right-click → Extract Here
- Or use: https://www.online-convert.com/en/file-converter/bz2-to-dat

## Step 6: Build C++ Module

```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection\cpp"
mkdir build
cd build

# Configure with vcpkg toolchain
cmake .. -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake

# Build
cmake --build . --config Release
```

## Step 7: Test

```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection"
python -c "import lockin_core; print('Success!')"
```

If you see "Success!", the module is built correctly!

## Step 8: Run the Daemon

```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection"
python app.py
```

The daemon will start on `http://127.0.0.1:8000` and open your camera.

## Troubleshooting

**CMake not found after installation:**
- Restart PowerShell completely
- Or manually add to PATH: `$env:Path += ";C:\Program Files\CMake\bin"`

**Build errors:**
- Make sure Visual Studio Build Tools are installed
- Verify vcpkg installed all dependencies
- Check CMakeLists.txt for path issues

**Import error:**
- Ensure module file exists: `fatigue_detection\lockin_core.pyd`
- Check Python architecture (64-bit recommended)
