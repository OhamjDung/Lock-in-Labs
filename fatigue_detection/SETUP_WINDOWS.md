# Windows Setup Guide for Fatigue Detection

## Prerequisites Installation

### 1. Install CMake

**Option A: Using Chocolatey (Recommended)**
```powershell
# Install Chocolatey first if you don't have it (run as Administrator)
Set-ExecutionPolicy Bypass -Scope Process -Force; [System.Net.ServicePointManager]::SecurityProtocol = [System.Net.ServicePointManager]::SecurityProtocol -bor 3072; iex ((New-Object System.Net.WebClient).DownloadString('https://community.chocolatey.org/install.ps1'))

# Install CMake
choco install cmake
```

**Option B: Download Installer**
1. Download CMake from: https://cmake.org/download/
2. Choose "Windows x64 Installer"
3. During installation, select "Add CMake to system PATH for all users" or "Add CMake to system PATH for current user"
4. Restart PowerShell after installation

**Option C: Using winget (Windows 10/11)**
```powershell
winget install Kitware.CMake
```

After installation, verify:
```powershell
cmake --version
```

### 2. Install C++ Compiler

**Option A: Visual Studio Build Tools (Recommended)**
1. Download Visual Studio Build Tools: https://visualstudio.microsoft.com/downloads/#build-tools-for-visual-studio-2022
2. Run installer and select "Desktop development with C++"
3. This includes MSVC compiler, CMake support, and Windows SDK

**Option B: Visual Studio Community (Full IDE)**
1. Download: https://visualstudio.microsoft.com/downloads/
2. Install "Desktop development with C++" workload

**Option C: MinGW-w64 (Alternative)**
```powershell
# Using Chocolatey
choco install mingw

# Or download from: https://www.mingw-w64.org/downloads/
```

### 3. Install Dependencies

#### OpenCV

**Option A: Using vcpkg (Recommended)**
```powershell
# Install vcpkg
git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
cd C:\vcpkg
.\bootstrap-vcpkg.bat

# Install OpenCV
.\vcpkg\vcpkg install opencv:x64-windows

# Install Dlib
.\vcpkg\vcpkg install dlib:x64-windows

# Integrate with Visual Studio
.\vcpkg\vcpkg integrate install
```

**Option B: Pre-built Binaries**
1. Download OpenCV from: https://opencv.org/releases/
2. Extract to `C:\opencv`
3. Set environment variable: `OpenCV_DIR=C:\opencv\build`

#### Dlib

**Using vcpkg (see above) or build from source:**
```powershell
# Download dlib
git clone https://github.com/davisking/dlib.git
cd dlib
mkdir build
cd build
cmake .. -DUSE_AVX_INSTRUCTIONS=ON
cmake --build . --config Release
```

#### Pybind11

**Using pip (simplest):**
```powershell
pip install pybind11
```

**Using vcpkg:**
```powershell
.\vcpkg\vcpkg install pybind11:x64-windows
```

#### Eigen3

**Using vcpkg:**
```powershell
.\vcpkg\vcpkg install eigen3:x64-windows
```

### 4. Download Dlib Landmark Model

```powershell
# Create models directory
mkdir fatigue_detection\models

# Download (requires 7zip or manual extraction)
# URL: http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
# Extract to: fatigue_detection\models\shape_predictor_68_face_landmarks.dat
```

Or use PowerShell to download and extract:
```powershell
cd fatigue_detection\models
Invoke-WebRequest -Uri "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2" -OutFile "shape_predictor_68_face_landmarks.dat.bz2"

# Requires 7zip or expand-archive alternative
# Extract using 7zip or online tool
```

### 5. Build the Module

**If using vcpkg, set toolchain:**
```powershell
cd fatigue_detection\cpp
mkdir build
cd build

# Use vcpkg toolchain
cmake .. -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake

# Build
cmake --build . --config Release
```

**If dependencies are installed manually, you may need to set paths:**
```powershell
cd fatigue_detection\cpp
mkdir build
cd build

# Set paths manually if needed
$env:OpenCV_DIR = "C:\opencv\build"
$env:Dlib_DIR = "C:\path\to\dlib\build"
$env:Eigen3_DIR = "C:\path\to\eigen3"

cmake ..
cmake --build . --config Release
```

## Quick Setup Script

Create `setup_windows.ps1` in project root:

```powershell
# Check for CMake
if (-not (Get-Command cmake -ErrorAction SilentlyContinue)) {
    Write-Host "CMake not found. Installing via winget..." -ForegroundColor Yellow
    winget install Kitware.CMake
    Write-Host "Please restart PowerShell and run this script again." -ForegroundColor Yellow
    exit
}

# Install Python dependencies
pip install -r fatigue_detection\requirements.txt

# Check for vcpkg
if (-not (Test-Path "C:\vcpkg")) {
    Write-Host "vcpkg not found. Installing..." -ForegroundColor Yellow
    git clone https://github.com/Microsoft/vcpkg.git C:\vcpkg
    cd C:\vcpkg
    .\bootstrap-vcpkg.bat
    cd ..
}

# Install dependencies via vcpkg
Write-Host "Installing dependencies via vcpkg..." -ForegroundColor Green
C:\vcpkg\vcpkg install opencv:x64-windows
C:\vcpkg\vcpkg install dlib:x64-windows
C:\vcpkg\vcpkg install pybind11:x64-windows
C:\vcpkg\vcpkg install eigen3:x64-windows

# Build module
Write-Host "Building C++ module..." -ForegroundColor Green
cd fatigue_detection\cpp
mkdir build -ErrorAction SilentlyContinue
cd build
cmake .. -DCMAKE_TOOLCHAIN_FILE=C:\vcpkg\scripts\buildsystems\vcpkg.cmake
cmake --build . --config Release

Write-Host "Setup complete!" -ForegroundColor Green
```

## Troubleshooting

### CMake not found after installation
- Restart PowerShell/terminal
- Check PATH: `$env:PATH -split ';' | Select-String cmake`
- Manually add CMake to PATH if needed

### Build errors about missing dependencies
- Verify all dependencies are installed
- Use vcpkg for easiest dependency management
- Check CMakeLists.txt paths

### Python can't import lockin_core
- Ensure module is built: `ls fatigue_detection\*.pyd`
- Check Python architecture matches (64-bit recommended)
- Verify module is in Python path
