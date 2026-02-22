# ANPR Pro - Quick Setup Script
# Run this script to set up the professional ANPR system

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ANPR Pro - Professional Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check Python version
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "✓ Python found: $pythonVersion" -ForegroundColor Green
} else {
    Write-Host "✗ Python not found. Please install Python 3.8 or higher." -ForegroundColor Red
    exit 1
}

# Create virtual environment (optional but recommended)
Write-Host ""
Write-Host "[2/5] Setting up virtual environment..." -ForegroundColor Yellow
$createVenv = Read-Host "Create virtual environment? (y/n)"
if ($createVenv -eq "y") {
    python -m venv venv
    Write-Host "✓ Virtual environment created" -ForegroundColor Green
    Write-Host "Activating virtual environment..." -ForegroundColor Yellow
    .\venv\Scripts\Activate.ps1
    Write-Host "✓ Virtual environment activated" -ForegroundColor Green
}

# Install dependencies
Write-Host ""
Write-Host "[3/5] Installing dependencies..." -ForegroundColor Yellow
Write-Host "This may take several minutes..." -ForegroundColor Gray

# Check if requirements_new.txt exists
if (Test-Path "requirements_new.txt") {
    pip install -r requirements_new.txt
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Dependencies installed successfully" -ForegroundColor Green
    } else {
        Write-Host "✗ Failed to install dependencies" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "✗ requirements_new.txt not found" -ForegroundColor Red
    exit 1
}

# Create necessary directories
Write-Host ""
Write-Host "[4/5] Creating directories..." -ForegroundColor Yellow
$directories = @("snapshots", "logs")
foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
        Write-Host "✓ Created $dir/" -ForegroundColor Green
    } else {
        Write-Host "✓ $dir/ already exists" -ForegroundColor Gray
    }
}

    '{}' | Out-File -FilePath "users.json" -Encoding UTF8
    Write-Host "✓ Created users.json" -ForegroundColor Green
}

# Initialize Database
if (-not (Test-Path "anpr.db")) {
    python -c "from database_utils import init_db; init_db()"
    Write-Host "✓ Initialized SQLite database (anpr.db)" -ForegroundColor Green
} else {
    Write-Host "✓ Database already exists" -ForegroundColor Gray
}

# Download YOLOv11 model
Write-Host ""
Write-Host "[5/5] Checking YOLO model..." -ForegroundColor Yellow
if (-not (Test-Path "yolo11n.pt")) {
    Write-Host "YOLOv11-Nano model will be downloaded on first run" -ForegroundColor Gray
    Write-Host "✓ Model check complete" -ForegroundColor Green
} else {
    Write-Host "✓ YOLOv11-Nano model found" -ForegroundColor Green
}

# Setup complete
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "1. Start the web application:" -ForegroundColor White
Write-Host "   python webapp.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "2. Open your browser and navigate to:" -ForegroundColor White
Write-Host "   http://localhost:5000" -ForegroundColor Cyan
Write-Host ""
Write-Host "3. Register a new account and start detecting!" -ForegroundColor White
Write-Host ""
Write-Host "For standalone detection (no web UI):" -ForegroundColor Yellow
Write-Host "   python anpr_engine.py" -ForegroundColor Cyan
Write-Host ""
Write-Host "For more information, see README_PRO.md" -ForegroundColor Gray
Write-Host ""
