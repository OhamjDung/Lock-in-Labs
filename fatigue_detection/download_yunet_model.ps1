# PowerShell script to download YuNet face detection model
# YuNet is a modern CNN-based face detector that handles rotation and glasses much better than HOG

Write-Host "Downloading YuNet Face Detection Model..." -ForegroundColor Cyan
Write-Host ""

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$modelsDir = Join-Path $scriptDir "models"

# Create models directory if it doesn't exist
if (-not (Test-Path $modelsDir)) {
    New-Item -ItemType Directory -Path $modelsDir | Out-Null
    Write-Host "Created models directory: $modelsDir" -ForegroundColor Green
}

# URL for YuNet model
$yunetUrl = "https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx"
$yunetPath = Join-Path $modelsDir "face_detection_yunet_2023mar.onnx"

# Download YuNet model (~85KB)
Write-Host "Downloading face_detection_yunet_2023mar.onnx..." -ForegroundColor Yellow
try {
    Invoke-WebRequest -Uri $yunetUrl -OutFile $yunetPath -UseBasicParsing
    Write-Host "[OK] Downloaded: $yunetPath" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Failed to download YuNet model: $_" -ForegroundColor Red
    Write-Host "  You can manually download from: $yunetUrl" -ForegroundColor Yellow
    Write-Host "  Save to: $yunetPath" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
if (Test-Path $yunetPath) {
    $fileSize = (Get-Item $yunetPath).Length / 1KB
    Write-Host "[SUCCESS] YuNet model downloaded successfully! ($([math]::Round($fileSize, 2)) KB)" -ForegroundColor Green
    Write-Host "  The face detector will now use YuNet for better detection." -ForegroundColor Cyan
    Write-Host "  This improves detection with head rotation and glasses significantly." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Next step: Rebuild the C++ module:" -ForegroundColor Yellow
    Write-Host "    cd fatigue_detection\cpp\build" -ForegroundColor Yellow
    Write-Host "    ..\..\rebuild_module.ps1" -ForegroundColor Yellow
} else {
    Write-Host "[ERROR] Model file not found after download." -ForegroundColor Red
    exit 1
}
