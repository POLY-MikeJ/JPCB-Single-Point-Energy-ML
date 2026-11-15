@echo off
setlocal
cd /d "%~dp0"
where python >nul 2>nul || (echo ERROR: Python 3.10-3.12 was not found. Install Python from python.org and select "Add Python to PATH". & exit /b 1)
if not exist ".venv\Scripts\python.exe" python -m venv .venv || (echo ERROR: Failed to create .venv. & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip --version || (echo ERROR: pip is not available in .venv. & exit /b 1)
python -m pip install -r requirements-lock.txt || exit /b 1
python -m pip install -e . || exit /b 1
echo Installation completed successfully.

