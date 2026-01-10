# Setup DLLs for lockin_core module
# This script copies all required DLLs from MSYS2 to fatigue_detection directory

$sourceDir = "C:\msys64\ucrt64\bin"
$destDir = "$PSScriptRoot"

Write-Host "Setting up DLLs for lockin_core..." -ForegroundColor Cyan

# Add MSYS2 bin to PATH
$env:Path = "$sourceDir;$env:Path"

# Copy all required DLLs
$dllPatterns = @(
    "libdlib*.dll",
    "libopencv*.dll",
    "libopenblas*.dll",
    "libgcc*.dll",
    "libstdc++*.dll",
    "libwinpthread*.dll",
    "libgfortran*.dll",
    "libquadmath*.dll"
)

$copied = 0
foreach ($pattern in $dllPatterns) {
    $files = Get-ChildItem -Path $sourceDir -Filter $pattern -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        $dest = Join-Path $destDir $file.Name
        Copy-Item $file.FullName -Destination $dest -Force -ErrorAction SilentlyContinue
        $copied++
    }
}

Write-Host "Copied $copied DLL(s) to $destDir" -ForegroundColor Green

# Test import
Write-Host "`nTesting module import..." -ForegroundColor Cyan
python -c "import lockin_core; print('SUCCESS! Module loaded.')" 2>&1
