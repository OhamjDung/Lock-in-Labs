# Copy required DLLs from MSYS2 to fatigue_detection directory
# This allows Python to load the lockin_core module

$sourceDir = "C:\msys64\ucrt64\bin"
$destDir = "D:\Noobcept\Lock In Labs\fatigue_detection"

Write-Host "Copying DLLs from $sourceDir to $destDir..." -ForegroundColor Cyan

# Copy all DLLs that might be needed
$dlls = @(
    "libdlib*.dll",
    "libopencv_*.dll", 
    "opencv_*.dll",
    "libopenblas*.dll",
    "libgcc_s_seh-*.dll",
    "libgcc_s_*.dll",
    "libgfortran*.dll",
    "libquadmath*.dll",
    "libwinpthread*.dll"
)

$copied = 0
foreach ($pattern in $dlls) {
    $files = Get-ChildItem "$sourceDir\$pattern" -ErrorAction SilentlyContinue
    foreach ($file in $files) {
        try {
            Copy-Item $file.FullName -Destination $destDir -Force -ErrorAction Stop
            Write-Host "  ✓ Copied: $($file.Name)" -ForegroundColor Green
            $copied++
        } catch {
            Write-Host "  ✗ Failed: $($file.Name)" -ForegroundColor Red
        }
    }
}

Write-Host "`nCopied $copied DLL(s)" -ForegroundColor Cyan
Write-Host "DLLs are now in: $destDir" -ForegroundColor Green
