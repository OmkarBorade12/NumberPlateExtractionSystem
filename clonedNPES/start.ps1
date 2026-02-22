# ANPR Quick Start - Camera Test & Launch
# This script tests your camera and starts the ANPR system

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  ANPR Pro - Quick Start" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 1: Test Camera
Write-Host "[1/3] Testing camera..." -ForegroundColor Yellow
Write-Host ""

python camera_diagnostic.py

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "Camera test completed. Check results above." -ForegroundColor Gray
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Step 2: Ask user what to do
Write-Host "[2/3] Choose how to start:" -ForegroundColor Yellow
Write-Host ""
Write-Host "  1. Web Application (Recommended)" -ForegroundColor White
Write-Host "     - Professional UI in browser" -ForegroundColor Gray
Write-Host "     - Dashboard with analytics" -ForegroundColor Gray
Write-Host "     - http://localhost:5000" -ForegroundColor Gray
Write-Host ""
Write-Host "  2. Standalone Detection" -ForegroundColor White
Write-Host "     - Direct camera window" -ForegroundColor Gray
Write-Host "     - Faster startup" -ForegroundColor Gray
Write-Host "     - No browser needed" -ForegroundColor Gray
Write-Host ""
Write-Host "  3. Interactive Demo" -ForegroundColor White
Write-Host "     - Test camera with live preview" -ForegroundColor Gray
Write-Host "     - Save screenshots" -ForegroundColor Gray
Write-Host "     - No detection, just preview" -ForegroundColor Gray
Write-Host ""
Write-Host "  4. Exit" -ForegroundColor White
Write-Host ""

$choice = Read-Host "Enter your choice (1-4)"

Write-Host ""
Write-Host "[3/3] Starting..." -ForegroundColor Yellow
Write-Host ""

switch ($choice) {
    "1" {
        Write-Host "Starting Web Application..." -ForegroundColor Green
        Write-Host ""
        Write-Host "The application will start on: http://localhost:5000" -ForegroundColor Cyan
        Write-Host "Your browser should open automatically." -ForegroundColor Gray
        Write-Host ""
        Write-Host "Press Ctrl+C to stop the server." -ForegroundColor Yellow
        Write-Host ""
        Start-Sleep -Seconds 2
        
        # Try to open browser
        Start-Process "http://localhost:5000"
        
        # Start webapp
        python webapp.py
    }
    "2" {
        Write-Host "Starting Standalone Detection..." -ForegroundColor Green
        Write-Host ""
        Write-Host "A window will open showing live detection." -ForegroundColor Gray
        Write-Host "Press 'Q' to quit." -ForegroundColor Yellow
        Write-Host ""
        Start-Sleep -Seconds 2
        python main.py
    }
    "3" {
        Write-Host "Starting Interactive Demo..." -ForegroundColor Green
        Write-Host ""
        Write-Host "Controls:" -ForegroundColor Gray
        Write-Host "  Q - Quit" -ForegroundColor Gray
        Write-Host "  S - Save screenshot" -ForegroundColor Gray
        Write-Host ""
        Start-Sleep -Seconds 2
        python camera_diagnostic.py
    }
    "4" {
        Write-Host "Exiting..." -ForegroundColor Gray
        exit 0
    }
    default {
        Write-Host "Invalid choice. Exiting..." -ForegroundColor Red
        exit 1
    }
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Session Ended" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
