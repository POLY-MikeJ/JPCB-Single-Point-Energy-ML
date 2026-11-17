@echo off
setlocal EnableExtensions
title ZHU MolEnergy Workbench Setup
cd /d "%~dp0"
set "PYINSTALLER=%~dp0runtime\python-3.13.5-amd64.exe"
set "PRIVATEPY=%~dp0_runtime\python.exe"
set "EXPECTED=C1CB40978B28F696B111C36034A1BDEDA17D25E35C74A08EF5E5FF405A63FC20"
if /I not "%PROCESSOR_ARCHITECTURE%"=="AMD64" (echo ERROR: Windows x64 is required.& pause & exit /b 2)
if not exist "%PYINSTALLER%" (echo ERROR: Bundled Python installer is missing.& pause & exit /b 2)
for /f "skip=1 tokens=*" %%H in ('certutil -hashfile "%PYINSTALLER%" SHA256 ^| findstr /R /V "hash CertUtil"') do if not defined ACTUAL set "ACTUAL=%%H"
set "ACTUAL=%ACTUAL: =%"
if /I not "%ACTUAL%"=="%EXPECTED%" (echo ERROR: Python installer checksum mismatch.& pause & exit /b 3)
if not exist "%PRIVATEPY%" (
  echo Installing private Python 3.13.5 runtime...
  "%PYINSTALLER%" /quiet InstallAllUsers=0 TargetDir="%~dp0_runtime" PrependPath=0 Include_launcher=0 Include_test=0 Include_doc=0 Shortcuts=0
  if errorlevel 1 (echo ERROR: Private Python installation failed.& pause & exit /b 4)
)
if not exist "%PRIVATEPY%" (echo ERROR: Private Python executable was not created.& pause & exit /b 4)
"%PRIVATEPY%" "%~dp0scripts\setup_windows.py"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (echo Setup failed. Review setup.log.& pause & exit /b %RC%)
echo Setup completed successfully. Use the desktop shortcut to start the workbench.
pause
exit /b 0
