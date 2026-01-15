cmake_minimum_required(VERSION 3.15)
project(fatigue_detection_cpp)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Build type
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Enable AVX for Dlib (if available)
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -mavx -mavx2")

# Find required packages
find_package(OpenCV REQUIRED)

# Find Eigen3 (header-only library, may not have CMake config)
find_package(Eigen3 QUIET)
if(NOT Eigen3_FOUND)
    # Try manual search for header-only Eigen
    find_path(EIGEN3_INCLUDE_DIR Eigen/Dense
        PATHS
        ${CMAKE_SOURCE_DIR}/../include/eigen3
        ${CMAKE_SOURCE_DIR}/../include
        C:/msys64/ucrt64/include/eigen3
        C:/msys64/mingw64/include/eigen3
        /usr/include/eigen3
        /usr/local/include/eigen3
        $ENV{EIGEN3_ROOT}/include
    )
    if(EIGEN3_INCLUDE_DIR)
        message(STATUS "Found Eigen3 (header-only): ${EIGEN3_INCLUDE_DIR}")
        set(EIGEN3_FOUND TRUE)
        # Create imported target for compatibility
        add_library(Eigen3::Eigen INTERFACE IMPORTED)
        set_target_properties(Eigen3::Eigen PROPERTIES
            INTERFACE_INCLUDE_DIRECTORIES "${EIGEN3_INCLUDE_DIR}"
        )
    else()
        message(FATAL_ERROR "Eigen3 not found. Install via: pacman -S mingw-w64-ucrt-x86_64-eigen3")
    endif()
endif()

# Find Dlib
find_path(DLIB_INCLUDE_DIR dlib/config.h
    PATHS
    ${CMAKE_SOURCE_DIR}/dlib
    ${CMAKE_SOURCE_DIR}/../dlib
    C:/msys64/ucrt64/include
    C:/msys64/mingw64/include
    /usr/include
    /usr/local/include
    $ENV{DLIB_ROOT}/include
)

find_library(DLIB_LIBRARY
    NAMES dlib
    PATHS
    ${CMAKE_SOURCE_DIR}/dlib
    C:/msys64/ucrt64/lib
    C:/msys64/mingw64/lib
    /usr/lib
    /usr/local/lib
    $ENV{DLIB_ROOT}/lib
)

if(NOT DLIB_INCLUDE_DIR OR NOT DLIB_LIBRARY)
    message(FATAL_ERROR "Dlib not found. Please install Dlib or set DLIB_ROOT environment variable.")
endif()

message(STATUS "Found Dlib: ${DLIB_LIBRARY}")
message(STATUS "Dlib include: ${DLIB_INCLUDE_DIR}")

# Find Python first (required by pybind11)
# Try to find Python 3.12 first, fallback to any Python 3.x
find_package(Python 3.12 EXACT COMPONENTS Interpreter Development QUIET)
if(NOT Python_FOUND)
    find_package(Python COMPONENTS Interpreter Development REQUIRED)
endif()
message(STATUS "Found Python: ${Python_EXECUTABLE}")
message(STATUS "Python version: ${Python_VERSION}")
message(STATUS "Python include dir: ${Python_INCLUDE_DIRS}")
message(STATUS "Python library: ${Python_LIBRARIES}")

# Pybind11 (can be installed via pip or MSYS2)
# Set policy to use FindPython instead of deprecated FindPythonLibs
set(PYBIND11_FINDPYTHON ON)

find_package(pybind11 QUIET)
if(NOT pybind11_FOUND)
    # Try to find via Python pip installation
    execute_process(
        COMMAND ${Python_EXECUTABLE} -c "import pybind11; print(pybind11.get_cmake_dir())"
        OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
        OUTPUT_STRIP_TRAILING_WHITESPACE
        ERROR_QUIET
    )
    if(PYBIND11_CMAKE_DIR)
        set(pybind11_DIR ${PYBIND11_CMAKE_DIR})
        find_package(pybind11 REQUIRED)
        message(STATUS "Found pybind11 via Python: ${PYBIND11_CMAKE_DIR}")
    else()
        # Try MSYS2 paths
        find_path(PYBIND11_CMAKE_DIR pybind11Config.cmake
            PATHS
            C:/msys64/ucrt64/lib/cmake/pybind11
            C:/msys64/mingw64/lib/cmake/pybind11
            /usr/lib/cmake/pybind11
            /usr/local/lib/cmake/pybind11
        )
        if(PYBIND11_CMAKE_DIR)
            set(pybind11_DIR ${PYBIND11_CMAKE_DIR})
            set(PYBIND11_FINDPYTHON ON)
            find_package(pybind11 REQUIRED)
            message(STATUS "Found pybind11: ${PYBIND11_CMAKE_DIR}")
        else()
            message(FATAL_ERROR "pybind11 not found. Install via: pip install pybind11 OR pacman -S mingw-w64-ucrt-x86_64-pybind11")
        endif()
    endif()
endif()

# nlohmann/json (header-only)
find_path(NLOHMANN_JSON_INCLUDE_DIR nlohmann/json.hpp
    PATHS
    C:/msys64/ucrt64/include
    C:/msys64/mingw64/include
    ${CMAKE_SOURCE_DIR}/../include
    ${CMAKE_BINARY_DIR}/_deps/json-include
    /usr/include
    /usr/local/include
)

if(NOT NLOHMANN_JSON_INCLUDE_DIR)
    message(WARNING "nlohmann/json not found. Will download single header file.")
    # Download single header file directly (no CMake needed)
    set(JSON_HEADER_DIR ${CMAKE_BINARY_DIR}/_deps/json-include)
    file(MAKE_DIRECTORY ${JSON_HEADER_DIR}/nlohmann)
    
    # Download the single header file
    file(DOWNLOAD 
        https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp
        ${JSON_HEADER_DIR}/nlohmann/json.hpp
        SHOW_PROGRESS
        STATUS DOWNLOAD_STATUS
    )
    
    list(GET DOWNLOAD_STATUS 0 STATUS_CODE)
    if(STATUS_CODE EQUAL 0)
        set(NLOHMANN_JSON_INCLUDE_DIR ${JSON_HEADER_DIR})
        message(STATUS "Downloaded nlohmann/json header to: ${NLOHMANN_JSON_INCLUDE_DIR}")
    else()
        message(FATAL_ERROR "Failed to download nlohmann/json. Please install manually or check internet connection.")
    endif()
endif()

message(STATUS "Found nlohmann/json: ${NLOHMANN_JSON_INCLUDE_DIR}")

# Include directories
include_directories(
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${OpenCV_INCLUDE_DIRS}
    ${DLIB_INCLUDE_DIR}
    ${NLOHMANN_JSON_INCLUDE_DIR}
)

# Add Eigen3 include (handle both CMake found and manual found)
if(Eigen3_FOUND)
    if(TARGET Eigen3::Eigen)
        # Use imported target
        # Already handled via target_link_libraries
    else()
        # Manual found, add include directory
        include_directories(${EIGEN3_INCLUDE_DIR})
    endif()
endif()

# Source files
set(SOURCES
    src/detector.cpp
    src/face_engine.cpp
    src/profile_manager.cpp
    src/detectors/yawn_detector.cpp
    src/detectors/gaze_detector.cpp
    src/detectors/fidget_detector.cpp
    src/detectors/neck_crack_detector.cpp
    src/bindings.cpp
)

# Header files
set(HEADERS
    src/detector.h
    src/face_engine.h
    src/profile_manager.h
    src/detectors/yawn_detector.h
    src/detectors/gaze_detector.h
    src/detectors/fidget_detector.h
    src/detectors/neck_crack_detector.h
)

# Create Python module
pybind11_add_module(lockin_core ${SOURCES} ${HEADERS})

# Find BLAS and LAPACK (required by Dlib for linear algebra)
find_library(LAPACK_LIBRARY
    NAMES lapack
    PATHS
    C:/msys64/ucrt64/lib
    C:/msys64/mingw64/lib
    /usr/lib
    /usr/local/lib
)

find_library(BLAS_LIBRARY
    NAMES blas openblas cblas
    PATHS
    C:/msys64/ucrt64/lib
    C:/msys64/mingw64/lib
    /usr/lib
    /usr/local/lib
)

# Link libraries
target_link_libraries(lockin_core PRIVATE
    ${OpenCV_LIBS}
    ${DLIB_LIBRARY}
)

# Link BLAS/LAPACK if found (required by Dlib)
if(LAPACK_LIBRARY)
    target_link_libraries(lockin_core PRIVATE ${LAPACK_LIBRARY})
    message(STATUS "Linking LAPACK: ${LAPACK_LIBRARY}")
endif()

if(BLAS_LIBRARY)
    target_link_libraries(lockin_core PRIVATE ${BLAS_LIBRARY})
    message(STATUS "Linking BLAS: ${BLAS_LIBRARY}")
endif()

# Link Eigen3 (header-only, but use target if available)
if(TARGET Eigen3::Eigen)
    target_link_libraries(lockin_core PRIVATE Eigen3::Eigen)
endif()

# Compiler-specific options
if(MSVC)
    target_compile_options(lockin_core PRIVATE /W4)
else()
    target_compile_options(lockin_core PRIVATE -Wall -Wextra -O3)
endif()

# Set output directory
set_target_properties(lockin_core PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/../..
)

message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
message(STATUS "OpenCV version: ${OpenCV_VERSION}")
message(STATUS "Eigen3 found: ${EIGEN3_FOUND}")
