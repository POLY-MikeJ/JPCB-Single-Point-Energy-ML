@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto validate_venv
where python >nul 2>nul || (echo ERROR: Python 3.10-3.13 was not found. Install Python from python.org and select "Add Python to PATH". & exit /b 1)
python -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,10),(3,11),(3,12),(3,13)] else 1)" || (echo ERROR: Unsupported Python version. Install 64-bit Python 3.10-3.13. & exit /b 1)
python -m venv .venv || (echo ERROR: Failed to create .venv. & exit /b 1)
:validate_venv
.venv\Scripts\python.exe -c "import sys; sys.exit(0 if sys.version_info[:2] in [(3,10),(3,11),(3,12),(3,13)] else 1)" || (echo ERROR: Existing .venv uses an unsupported Python version. Remove .venv and install Python 3.10-3.13. & exit /b 1)
call .venv\Scripts\activate.bat
python -m pip --version || (echo ERROR: pip is not available in .venv. & exit /b 1)
python -m pip install -r requirements-lock.txt || exit /b 1
python -m pip install -e . || exit /b 1
echo Installation completed successfully.

