# Quick Fix: Python Version Mismatch

## Problem
The `lockin_core` module is compiled for Python 3.13, but you're running Python 3.12.

## Solution Options

### Option 1: Rebuild Module for Python 3.12 (Recommended)

Run the rebuild script:
```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection"
.\rebuild_module.ps1
```

**Prerequisites:**
- MSYS2 installed at `C:\msys64`
- Dependencies installed (if not, see BUILD_INSTRUCTIONS.md)

### Option 2: Use Python 3.13 (If Available)

If you have Python 3.13 installed:
```powershell
# Find Python 3.13
Get-ChildItem "C:\Users\$env:USERNAME\AppData\Local\Programs\Python\" -Directory

# Use Python 3.13 explicitly
C:\Users\$env:USERNAME\AppData\Local\Programs\Python\Python313\python.exe fatigue_detection/calibration_cli.py --user test --work-duration 1 --break-duration 1
```

### Option 3: Quick Test Without C++ Module (Limited)

For testing the calibration flow without the C++ module, you could modify `engine.py` temporarily, but this won't provide actual fatigue detection.

## Recommended: Rebuild

The rebuild script (`rebuild_module.ps1`) will:
1. Detect your Python version
2. Clean previous build
3. Configure CMake
4. Build the module
5. Copy it to the correct location
6. Test the import

**Time:** 5-15 minutes depending on your CPU.

**If rebuild fails:** See `fatigue_detection/BUILD_INSTRUCTIONS.md` for detailed setup.
