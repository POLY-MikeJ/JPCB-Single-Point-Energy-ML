@echo off
setlocal
cd /d "%~dp0"
set "JPCB_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%JPCB_PYTHON%" (
  echo ERROR: Project Python was not found: %JPCB_PYTHON%
  pause
  exit /b 2
)
"%JPCB_PYTHON%" "%~dp0scripts\launcher.py" stop
if errorlevel 1 pause
