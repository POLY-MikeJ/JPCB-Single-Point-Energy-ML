@echo off
setlocal
cd /d "%~dp0"
set "ZHU_MOLENERGY_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%ZHU_MOLENERGY_PYTHON%" (
  echo ERROR: Project Python was not found:
  echo %ZHU_MOLENERGY_PYTHON%
  echo Run install_windows.bat once from this project folder.
  pause
  exit /b 2
)
"%ZHU_MOLENERGY_PYTHON%" "%~dp0scripts\launcher.py" start
if errorlevel 1 pause
