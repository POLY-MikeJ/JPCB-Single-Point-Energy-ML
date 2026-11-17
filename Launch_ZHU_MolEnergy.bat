@echo off
rem Compatibility alias retained for existing users and old shortcuts.
setlocal
set "ZHU_MOLENERGY_PYTHON=%~dp0.venv\Scripts\python.exe"
if not exist "%ZHU_MOLENERGY_PYTHON%" (
  echo ERROR: Existing project Python was not found: %ZHU_MOLENERGY_PYTHON%
  pause
  exit /b 2
)
call "%~dp0Start_ZHU_MolEnergy.bat"
exit /b %ERRORLEVEL%
