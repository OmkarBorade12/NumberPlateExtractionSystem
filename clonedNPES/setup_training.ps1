# ANPR Custom Model Training - PowerShell Script

Write-Host "=====================================================================" -ForegroundColor Cyan
Write-Host "ANPR Custom Model Training Setup" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan

# Step 1: Create training directory
Write-Host "`n[1/6] Creating training directory..." -ForegroundColor Yellow
if (!(Test-Path "training")) {
    New-Item -ItemType Directory -Path "training" | Out-Null
    Write-Host "[OK] Created training directory" -ForegroundColor Green
} else {
    Write-Host "[OK] Training directory already exists" -ForegroundColor Green
}

# Step 2: Clone YOLOv9 repository
Write-Host "`n[2/6] Cloning YOLOv9 repository..." -ForegroundColor Yellow
if (!(Test-Path "training\yolov9")) {
    Set-Location training
    git clone https://github.com/SkalskiP/yolov9.git
    Set-Location ..
    Write-Host "[OK] Cloned YOLOv9 repository" -ForegroundColor Green
} else {
    Write-Host "[OK] YOLOv9 repository already exists" -ForegroundColor Green
}

# Step 3: Install requirements
Write-Host "`n[3/6] Installing requirements..." -ForegroundColor Yellow
if (Test-Path "training\yolov9\requirements.txt") {
    Set-Location training\yolov9
    pip install -r requirements.txt
    pip install roboflow
    Set-Location ..\..
    Write-Host "[OK] Requirements installed" -ForegroundColor Green
} else {
    Write-Host "[Error] training\yolov9\requirements.txt not found!" -ForegroundColor Red
}

# Step 4: Download pre-trained weights
Write-Host "`n[4/6] Downloading pre-trained weights..." -ForegroundColor Yellow
if (!(Test-Path "training\yolov9\weights")) {
    New-Item -ItemType Directory -Path "training\yolov9\weights" | Out-Null
}

if (!(Test-Path "training\yolov9\weights\gelan-c.pt")) {
    Write-Host "Downloading gelan-c.pt (51MB)..." -ForegroundColor Cyan
    try {
        Invoke-WebRequest -Uri "https://github.com/WongKinYiu/yolov9/releases/download/v0.1/gelan-c.pt" -OutFile "training\yolov9\weights\gelan-c.pt"
        Write-Host "[OK] Downloaded gelan-c.pt" -ForegroundColor Green
    } catch {
        Write-Host "[Error] Failed to download weights: $_" -ForegroundColor Red
    }
} else {
    Write-Host "[OK] gelan-c.pt already exists" -ForegroundColor Green
}

# Step 5: Information about dataset
Write-Host "`n[5/6] Dataset Information" -ForegroundColor Yellow
Write-Host "Dataset: ANPR2 (Roboflow)" -ForegroundColor Cyan
Write-Host "Source: https://universe.roboflow.com/arvind-kumar-wjygd/anpr2-syxl7" -ForegroundColor Cyan
Write-Host "`nTo download the dataset, you will need a Roboflow API key" -ForegroundColor White
Write-Host "Get your API key from: https://app.roboflow.com/auth-cli" -ForegroundColor White

# Step 6: Training instructions
Write-Host "`n[6/6] Training Instructions" -ForegroundColor Yellow
Write-Host "`nOption A: Use Python Script (Recommended)" -ForegroundColor Cyan
Write-Host "  python train_custom_model.py" -ForegroundColor White

Write-Host "`n=====================================================================" -ForegroundColor Cyan
Write-Host "[OK] Setup Complete!" -ForegroundColor Green
Write-Host "=====================================================================" -ForegroundColor Cyan

Write-Host "`nNext Steps:" -ForegroundColor Yellow
Write-Host "1. Run: python train_custom_model.py" -ForegroundColor White
Write-Host "2. Follow the interactive prompts" -ForegroundColor White
Write-Host "3. Wait for training to complete (~30-60 minutes)" -ForegroundColor White
Write-Host "4. Integrate the trained model into your ANPR system" -ForegroundColor White
