"""Test script with detailed DLL error reporting."""

import os
import sys
import ctypes

# Set PATH for DLLs
msys2_bin = r"C:\msys64\ucrt64\bin"
os.environ["PATH"] = msys2_bin + os.pathsep + os.environ.get("PATH", "")

print("Testing lockin_core import with DLL debugging...")
print(f"Python: {sys.executable}")
print(f"Python version: {sys.version}")
print(f"Current directory: {os.getcwd()}")
print(f"Module file: lockin_core.cp313-win_amd64.pyd")
print(f"Module exists: {os.path.exists('lockin_core.cp313-win_amd64.pyd')}")
print(f"PATH: {os.environ.get('PATH', '')[:200]}...")

# Add current directory to Python path
sys.path.insert(0, os.getcwd())

try:
    # Try to load the module
    import lockin_core
    print("\n✅ SUCCESS! Module loaded successfully!")
    print(f"Version: {lockin_core.__version__}")
    
except ImportError as e:
    print(f"\n❌ ImportError: {e}")
    print("\nThis usually means a DLL dependency is missing.")
    print("\nTroubleshooting steps:")
    print("1. Ensure all DLLs are in the same directory as the .pyd file")
    print("2. Check if MSYS2 bin is in PATH")
    print("3. Verify DLL architecture matches (64-bit)")
    
    # Try to get more info using Windows error
    error_code = ctypes.get_last_error()
    if error_code:
        print(f"Windows error code: {error_code}")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
