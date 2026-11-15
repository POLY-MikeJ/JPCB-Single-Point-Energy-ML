@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (echo ERROR: Run install_windows.bat first. & exit /b 1)
call .venv\Scripts\activate.bat
start "" http://localhost:8501
python -m streamlit run src\jpcb_energy\app.py --server.headless=true --browser.gatherUsageStats=false

