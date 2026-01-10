# CMake Configuration Script for Fatigue Detection
# Run this after installing dependencies via MSYS2

cd "D:\Noobcept\Lock In Labs\fatigue_detection\cpp\build"

# Clean previous attempts
Remove-Item CMakeCache.txt -ErrorAction SilentlyContinue
Remove-Item CMakeFiles -Recurse -ErrorAction SilentlyContinue

# Try ucrt64 first (most common)
$OPENCV_DIR = "C:\msys64\ucrt64\lib\cmake\opencv4"
$DLIB_DIR = "C:\msys64\ucrt64\lib\cmake"
$EIGEN_DIR = "C:\msys64\ucrt64\share\eigen3\cmake"

# Check if ucrt64 paths exist, otherwise try mingw64
if (-not (Test-Path $OPENCV_DIR)) {
    Write-Host "ucrt64 not found, trying mingw64..." -ForegroundColor Yellow
    $OPENCV_DIR = "C:\msys64\mingw64\lib\cmake\opencv4"
    $DLIB_DIR = "C:\msys64\mingw64\lib\cmake"
    $EIGEN_DIR = "C:\msys64\mingw64\share\eigen3\cmake"
}

# Verify paths exist
if (-not (Test-Path $OPENCV_DIR)) {
    Write-Host "ERROR: OpenCV not found. Please install dependencies via MSYS2:" -ForegroundColor Red
    Write-Host "  1. Open MSYS2 UCRT64 terminal (C:\msys64\ucrt64.exe)" -ForegroundColor Yellow
    Write-Host "  2. Run: pacman -S mingw-w64-ucrt-x86_64-opencv" -ForegroundColor Yellow
    Write-Host "  3. Run: pacman -S mingw-w64-ucrt-x86_64-dlib" -ForegroundColor Yellow
    Write-Host "  4. Run: pacman -S mingw-w64-ucrt-x86_64-eigen3" -ForegroundColor Yellow
    Write-Host "  5. Run: pacman -S mingw-w64-ucrt-x86_64-pybind11" -ForegroundColor Yellow
    exit 1
}

Write-Host "Configuring CMake with:" -ForegroundColor Green
Write-Host "  OpenCV: $OPENCV_DIR" -ForegroundColor Cyan
Write-Host "  Dlib: $DLIB_DIR" -ForegroundColor Cyan
Write-Host "  Eigen: $EIGEN_DIR" -ForegroundColor Cyan

# Configure CMake
cmake .. -G "MinGW Makefiles" `
  -DCMAKE_C_COMPILER=gcc `
  -DCMAKE_CXX_COMPILER=g++ `
  -DOpenCV_DIR="$OPENCV_DIR" `
  -DDlib_DIR="$DLIB_DIR" `
  -DEigen3_DIR="$EIGEN_DIR"

if ($LASTEXITCODE -eq 0) {
    Write-Host "`n✅ CMake configuration successful!" -ForegroundColor Green
    Write-Host "Next step: Run 'mingw32-make' to build" -ForegroundColor Cyan
} else {
    Write-Host "`n❌ CMake configuration failed. Check errors above." -ForegroundColor Red
}
