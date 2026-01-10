# Runtime Setup Instructions

## DLL Dependencies

The `lockin_core` module requires DLLs from MSYS2. These need to be accessible when Python loads the module.

### Option 1: Add MSYS2 to System PATH (Recommended for Development)

1. Add `C:\msys64\ucrt64\bin` to your system PATH
2. Restart Cursor/PowerShell
3. Verify: `python -c "import lockin_core; print('Success')"`

### Option 2: Copy DLLs to Module Directory (Recommended for Deployment)

Run the setup script to copy all required DLLs:

```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection"
.\setup_dlls.ps1
```

This copies ~65 DLL files (OpenCV, Dlib, OpenBLAS, MinGW runtime) to the `fatigue_detection/` directory.

### Option 3: Set PATH in Script (Current Implementation)

The `app.py` and `engine.py` already set PATH programmatically:
- `app.py` adds MSYS2 bin to PATH on startup
- `engine.py` adds MSYS2 bin to PATH before importing lockin_core

**This should work automatically when running `python app.py`.**

## Testing

```powershell
cd "D:\Noobcept\Lock In Labs\fatigue_detection"

# Test module import
python -c "from fatigue_detection.engine import FatigueEngine; print('SUCCESS')"

# Or run the daemon
python app.py
```

## Troubleshooting

### "DLL load failed"
- Ensure MSYS2 bin is in PATH: `$env:Path -like "*msys64*"`
- Or copy DLLs to module directory using `setup_dlls.ps1`
- Check if all DLLs exist: `Get-ChildItem fatigue_detection\*.dll | Measure-Object`

### "ModuleNotFoundError: No module named 'lockin_core'"
- Check if .pyd file exists: `Get-ChildItem fatigue_detection\*.pyd`
- Verify Python path: `python -c "import sys; print(sys.path)"`
- Ensure you're using system Python, not MSYS2 Python: `where.exe python`

### "ModuleNotFoundError: No module named 'numpy'"
- This means you're using MSYS2 Python instead of system Python
- Use full path to system Python or remove MSYS2 from PATH
