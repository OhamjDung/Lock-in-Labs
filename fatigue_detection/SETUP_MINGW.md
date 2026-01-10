# Setting Up with MinGW/MSYS2

You're using MSYS2 with MinGW, which is perfect! Here's how to install the dependencies.

## Install Dependencies via MSYS2

Open **MSYS2 UCRT64** terminal (or your MinGW terminal) and run:

```bash
# Update package database
pacman -Syu

# Install OpenCV
pacman -S mingw-w64-ucrt-x86_64-opencv

# Install Dlib
pacman -S mingw-w64-ucrt-x86_64-dlib

# Install Eigen3
pacman -S mingw-w64-ucrt-x86_64-eigen3

# Install Pybind11
pacman -S mingw-w64-ucrt-x86_64-pybind11

# Install CMake (if not installed)
pacman -S mingw-w64-ucrt-x86_64-cmake
```

## Set Environment Variables

After installing, you may need to tell CMake where to find these packages:

```powershell
# In PowerShell (from your project directory)
cd "D:\Noobcept\Lock In Labs\fatigue_detection\cpp\build"

# Set paths (adjust if your MSYS2 is in different location)
$env:OpenCV_DIR = "C:\msys64\ucrt64\lib\cmake\opencv4"
$env:Dlib_DIR = "C:\msys64\ucrt64\lib\cmake"
$env:Eigen3_DIR = "C:\msys64\ucrt64\share\eigen3\cmake"

# Configure CMake
cmake .. -G "MinGW Makefiles" -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++

# Build
mingw32-make
```

## Alternative: Build Dependencies from Source

If MSYS2 packages don't work or aren't available, you can build from source in MSYS2 terminal.

## Download Dlib Landmark Model

You still need the Dlib 68-point landmark model:

```bash
cd "D:\Noobcept\Lock In Labs\fatigue_detection\models"
wget http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2
bunzip2 shape_predictor_68_face_landmarks.dat.bz2
```

Or use PowerShell:
```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection\models"
Invoke-WebRequest -Uri "http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2" -OutFile "shape_predictor_68_face_landmarks.dat.bz2"
# Extract using 7-Zip or online tool
```
