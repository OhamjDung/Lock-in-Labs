#!/usr/bin/env python
"""Test script to verify lockin_core module can be imported."""

import sys
import os

# Add MSYS2 bin to PATH for DLLs
msys2_bin = r"C:\msys64\ucrt64\bin"
if os.path.exists(msys2_bin):
    os.environ["PATH"] = msys2_bin + os.pathsep + os.environ.get("PATH", "")

print("Testing lockin_core import...")
print(f"Python: {sys.executable}")
print(f"CWD: {os.getcwd()}")
print(f"Module file exists: {os.path.exists('lockin_core.cp313-win_amd64.pyd')}")

try:
    import lockin_core
    print("✅ SUCCESS! Module loaded successfully!")
    print(f"Version: {lockin_core.__version__}")
    
    # Test creating an engine instance
    engine = lockin_core.FatigueEngine("test_user")
    print("✅ Engine created successfully!")
    
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print("\nTroubleshooting:")
    print(f"1. Check if lockin_core.pyd exists in: {os.getcwd()}")
    print(f"2. Check if DLLs are in PATH: {msys2_bin}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
