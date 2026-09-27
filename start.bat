@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
".venv\Scripts\python.exe" -c "import tkinter, yt_dlp, deno, imageio_ffmpeg" >nul 2>&1
if errorlevel 1 (
    echo Missing components. Running setup...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup.ps1"
    if errorlevel 1 (
        pause
        exit /b 1
    )
)
start "" ".venv\Scripts\pythonw.exe" "%~dp0app.py"
