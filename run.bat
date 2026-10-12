@echo off
title YouTube Downloader
echo ===================================================
echo     Starting YouTube Downloader Local Web App
echo ===================================================
cd /d "%~dp0"

:: 1. Check if Python is installed and available in PATH
where python >nul 2>&1
if %errorlevel% neq 0 (
    where py >nul 2>&1
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Python is not found on your system!
        echo Please download and install Python 3.10+ from:
        echo https://www.python.org/downloads/
        echo (Make sure to check "Add Python to PATH" during installation)
        echo.
        pause
        exit /b 1
    )
)

:: 2. Check if dependencies are installed, install if missing
echo Checking dependencies...
python -c "import flask, yt_dlp, imageio_ffmpeg" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing missing requirements from requirements.txt...
    python -m pip install -r requirements.txt
    if %errorlevel% neq 0 (
        echo.
        echo [ERROR] Failed to install required packages.
        echo Please check your internet connection or run:
        echo   python -m pip install -r requirements.txt
        echo.
        pause
        exit /b 1
    )
)

:: 3. Launch application
echo.
echo Launching YouTube Downloader...
python app.py
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] The application stopped unexpectedly.
    pause
)
