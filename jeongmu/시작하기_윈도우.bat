@echo off
chcp 65001 > nul
set PYTHONUTF8=1
cd /d "%~dp0"
where python > nul 2>&1
if errorlevel 1 (
  echo Python is not installed. Install it from https://www.python.org/downloads/ and tick "Add python.exe to PATH".
  start https://www.python.org/downloads/
  pause
  exit /b 1
)
python first_run.py
pause
