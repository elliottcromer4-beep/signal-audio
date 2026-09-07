@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto ready
echo Setting up Signal. This only happens once.
py -3.11 -m venv .venv
if errorlevel 1 (
  echo Please install Python 3.11 from python.org, then run this file again.
  pause
  exit /b 1
)
:ready
".venv\Scripts\python.exe" -c "import faster_whisper, tkinter, pyaudiowpatch" >nul 2>&1
if not errorlevel 1 goto launch
".venv\Scripts\python.exe" -m pip install -r requirements-lock.txt
if errorlevel 1 (
  echo Setup failed. Check your internet connection and try again.
  pause
  exit /b 1
)
:launch
".venv\Scripts\python.exe" app.py
if errorlevel 1 pause
