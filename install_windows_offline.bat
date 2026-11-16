@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo ERROR: Python 3.10-3.13 was not found. & exit /b 1)
if not exist "wheelhouse" (echo ERROR: wheelhouse is missing. Run prepare_offline_windows.ps1 on a connected computer first. & exit /b 1)
if not exist ".venv\Scripts\python.exe" python -m venv .venv || exit /b 1
call .venv\Scripts\activate.bat
python -m pip install --no-index --find-links wheelhouse -r requirements-lock.txt || exit /b 1
python -m pip install --no-index --no-deps -e . || exit /b 1
echo Offline installation completed successfully.
