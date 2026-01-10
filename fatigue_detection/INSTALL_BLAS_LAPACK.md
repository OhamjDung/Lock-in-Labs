# Install BLAS/LAPACK for Dlib

Dlib requires BLAS and LAPACK libraries for linear algebra operations. These are missing from your system.

## Install via MSYS2

Open **MSYS2 UCRT64 terminal** and run:

```bash
pacman -S mingw-w64-ucrt-x86_64-openblas
pacman -S mingw-w64-ucrt-x86_64-lapack
```

This installs OpenBLAS which provides both BLAS and LAPACK functionality.

## After Installation

1. Reconfigure CMake:
   ```powershell
   cd "D:\Noobcept\Lock In Labs\fatigue_detection\cpp\build"
   Remove-Item CMakeCache.txt -ErrorAction SilentlyContinue
   cmake .. -G "MinGW Makefiles" -DCMAKE_C_COMPILER=gcc -DCMAKE_CXX_COMPILER=g++ -DOpenCV_DIR="C:\msys64\ucrt64\lib\cmake\opencv4"
   ```

2. Build again:
   ```powershell
   mingw32-make
   ```

## Alternative: Link Order Fix

If libraries are installed but not found, the link order might be wrong. The CMakeLists.txt has been updated to search for them.
