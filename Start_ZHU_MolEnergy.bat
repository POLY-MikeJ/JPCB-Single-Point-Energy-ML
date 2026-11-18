@echo off
setlocal
title ZHU MolEnergy Workbench Launcher
cd /d "%~dp0"
set "ZHU_MOLENERGY_PYTHON=%~dp0.venv\Scripts\python.exe"
set "ZHU_MOLENERGY_ROOT=%~dp0"
if exist "%~dp0runtime\xtb\xtb.exe" (
  set "XTB_EXE=%~dp0runtime\xtb\xtb.exe"
  set "XTBPATH=%~dp0runtime\xtb\share\xtb"
  set "PATH=%~dp0runtime\xtb;%PATH%"
)
if not exist "%ZHU_MOLENERGY_PYTHON%" (
  echo ERROR: Existing project virtual environment was not found:
  echo %ZHU_MOLENERGY_PYTHON%
  echo No installation or environment rebuild was attempted.
  pause
  exit /b 2
)
if not exist "%~dp0scripts\launcher.py" (
  echo ERROR: Launcher module is missing: %~dp0scripts\launcher.py
  pause
  exit /b 2
)
echo Starting ZHU MolEnergy Workbench with the existing project environment...
"%ZHU_MOLENERGY_PYTHON%" "%~dp0scripts\launcher.py" start --foreground
set "ZHU_MOLENERGY_EXIT=%ERRORLEVEL%"
if not "%ZHU_MOLENERGY_EXIT%"=="0" (
  echo.
  echo Startup failed. Review local_jobs\zhu_molenergy_launcher\zhu_molenergy_streamlit.log
  pause
)
exit /b %ZHU_MOLENERGY_EXIT%
