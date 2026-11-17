# Windows installation

Use 64-bit Windows 10 or 11 and Python 3.10-3.13. Download Python from python.org and enable **Add Python to PATH**. Double-click `install_windows.bat`; it checks the Python version, creates project-local `.venv`, installs pinned CPU dependencies, and installs the package.

Double-click `Start_ZHU_MolEnergy.bat` to open ZHU MolEnergy Workbench. It invokes `.venv\Scripts\python.exe` directly, renders a real application preflight, binds to `127.0.0.1`, selects a free port, waits for Streamlit health, and then opens the browser. After `.venv` exists, system `python` and `py` commands are not required. Paths containing spaces and non-ASCII characters are supported. `Launch_ZHU_MolEnergy.bat` remains a compatibility alias.

Double-click `Install_ZHU_MolEnergy_Desktop_Shortcut.bat` to create the per-user shortcut **ZHU MolEnergy Workbench** without administrator rights. The installer removes the old project-created JPCB shortcut only after confirming that its target belongs to this project. `Stop_ZHU_MolEnergy.bat` targets only the PID recorded by this launcher.

For offline use, run `prepare_offline_windows.ps1` on a connected computer with the same Python minor version. Copy the generated `wheelhouse` with the repository and run `install_windows_offline.bat`. No runtime CDN or cloud service is required. PyInstaller is not used because RDKit/Mordred packaging was not validated as reliably as the tested virtual-environment launcher.

`requirements-lock.txt` pins the supported direct dependencies. `requirements-windows-lock.txt` records the complete transitive environment resolved and tested on Windows x86-64 with CPython 3.13.5 and `include-system-site-packages=false`; install the local project after that lock file. The development package remains compatible with Python 3.10-3.13, while wheel availability must be checked for the selected minor version.

