# Rebuild lockin_core module for current Python version
# This script rebuilds the C++ module to match your Python version

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Rebuilding lockin_core Module" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$buildDir = Join-Path $scriptDir "cpp\build"

# Check Python version
Write-Host "[1/5] Checking Python version..." -ForegroundColor Green
$pythonVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Host "  Python version: $pythonVersion" -ForegroundColor White

# Check if build directory exists
if (-not (Test-Path $buildDir)) {
    Write-Host "[2/5] Creating build directory..." -ForegroundColor Green
    New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
}

# Navigate to build directory
Set-Location $buildDir

# Clean previous build
Write-Host "[2/5] Cleaning previous build..." -ForegroundColor Green
Remove-Item CMakeCache.txt -ErrorAction SilentlyContinue
Remove-Item CMakeFiles -Recurse -ErrorAction SilentlyContinue -Force
Remove-Item *.pyd -ErrorAction SilentlyContinue

# Configure CMake
Write-Host "[3/5] Configuring CMake..." -ForegroundColor Green
Write-Host "  This may take a minute..." -ForegroundColor Gray

$cmakeArgs = @(
    "..",
    "-G", "MinGW Makefiles",
    "-DCMAKE_C_COMPILER=gcc",
    "-DCMAKE_CXX_COMPILER=g++",
    "-DOpenCV_DIR=C:\msys64\ucrt64\lib\cmake\opencv4",
    "-DDlib_DIR=C:\msys64\ucrt64\lib\cmake",
    "-DEigen3_DIR=C:\msys64\ucrt64\share\eigen3\cmake"
)

$cmakeResult = & cmake @cmakeArgs 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] CMake configuration failed!" -ForegroundColor Red
    Write-Host $cmakeResult -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure:" -ForegroundColor Yellow
    Write-Host "  1. MSYS2 is installed at C:\msys64" -ForegroundColor Yellow
    Write-Host "  2. Dependencies are installed: pacman -S mingw-w64-ucrt-x86_64-opencv mingw-w64-ucrt-x86_64-dlib mingw-w64-ucrt-x86_64-eigen3 mingw-w64-ucrt-x86_64-pybind11" -ForegroundColor Yellow
    exit 1
}

Write-Host "[OK] CMake configured successfully" -ForegroundColor Green

# Build the module
Write-Host "[4/5] Building module (this may take 5-15 minutes)..." -ForegroundColor Green
Write-Host "  Please be patient..." -ForegroundColor Gray

$buildResult = & mingw32-make 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Build failed!" -ForegroundColor Red
    Write-Host $buildResult -ForegroundColor Red
    exit 1
}

Write-Host "[OK] Build completed successfully" -ForegroundColor Green

# Copy module to fatigue_detection directory
Write-Host "[5/5] Copying module..." -ForegroundColor Green
$pydFiles = Get-ChildItem -Path $buildDir -Filter "*.pyd" -ErrorAction SilentlyContinue

if ($pydFiles.Count -eq 0) {
    Write-Host "[ERROR] No .pyd file found in build directory!" -ForegroundColor Red
    exit 1
}

$targetFile = Join-Path $scriptDir $pydFiles[0].Name
Copy-Item $pydFiles[0].FullName -Destination $targetFile -Force

Write-Host "  Copied: $($pydFiles[0].Name) -> $targetFile" -ForegroundColor White

# Test import
Write-Host ""
Write-Host "[TEST] Testing module import..." -ForegroundColor Green
Set-Location $scriptDir
$testResult = python -c "import lockin_core; print('SUCCESS: Module loaded!')" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host $testResult -ForegroundColor Green
    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Build Complete!" -ForegroundColor Cyan
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "The module has been rebuilt for Python $pythonVersion" -ForegroundColor White
} else {
    Write-Host "[WARNING] Module built but import test failed:" -ForegroundColor Yellow
    Write-Host $testResult -ForegroundColor Yellow
    Write-Host ""
    Write-Host "You may need to copy DLLs. See setup_dlls.ps1" -ForegroundColor Yellow
}
