@echo off
setlocal EnableExtensions EnableDelayedExpansion
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
rem The PSF installer enters maintenance mode when the identical per-user
rem Python is already registered and may ignore a new TargetDir.  In that
rem case copy the registered PSF runtime locally so this installation remains
rem self-contained.  Never fall back to PATH or an Anaconda installation.
if not exist "%PRIVATEPY%" (
  for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Python\PythonCore\3.13\InstallPath" /ve 2^>nul ^| findstr /I "REG_SZ"') do set "REGISTEREDROOT=%%B"
  if defined REGISTEREDROOT if exist "!REGISTEREDROOT!python.exe" (
    echo Python 3.13 is already registered; copying that PSF runtime locally...
    xcopy "!REGISTEREDROOT!*" "%~dp0_runtime\" /E /I /H /K /Y >nul
    if errorlevel 2 (echo ERROR: Existing PSF Python runtime could not be copied.& pause & exit /b 4)
  )
)
if not exist "%PRIVATEPY%" (echo ERROR: Private Python executable was not created.& pause & exit /b 4)
"%PRIVATEPY%" -c "import platform; print(platform.python_version())" > "%~dp0_runtime\python-version.txt"
set /p PRIVATEVER=<"%~dp0_runtime\python-version.txt"
del /q "%~dp0_runtime\python-version.txt" >nul 2>&1
if not "%PRIVATEVER%"=="3.13.5" (echo ERROR: Bundled runtime must be official Python 3.13.5, found %PRIVATEVER%.& pause & exit /b 4)
"%PRIVATEPY%" "%~dp0scripts\setup_windows.py"
set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (echo Setup failed. Review setup.log.& pause & exit /b %RC%)
echo Setup completed successfully. Use the desktop shortcut to start the workbench.
pause
exit /b 0
