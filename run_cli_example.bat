@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo ERROR: Run install_windows.bat first. & exit /b 1)
call .venv\Scripts\activate.bat
python scripts\predict_v11.py "C=CC(=O)N" --model-id v1.1.0-gpr-water

