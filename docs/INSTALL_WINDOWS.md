# Windows installation

Use 64-bit Windows 10 or 11 and Python 3.10-3.13. Download Python from python.org and enable **Add Python to PATH**. Double-click `install_windows.bat`; it checks the Python version, creates project-local `.venv`, installs pinned CPU dependencies, and installs the package.

Double-click `Launch_JPCB_Workbench.bat` to open the local application. It invokes `.venv\Scripts\python.exe` directly, binds to `127.0.0.1`, selects a free port, waits for Streamlit health, and then opens the browser. After `.venv` exists, system `python` and `py` commands are not required. Paths containing spaces and non-ASCII characters are supported.

Double-click `Install_Desktop_Shortcut.bat` to create the per-user shortcut **JPCB Molecular Energy Workbench** without administrator rights. `Stop_JPCB_Workbench.bat` targets only the PID recorded by this launcher.

For offline use, run `prepare_offline_windows.ps1` on a connected computer with the same Python minor version. Copy the generated `wheelhouse` with the repository and run `install_windows_offline.bat`. No runtime CDN or cloud service is required. PyInstaller is not used because RDKit/Mordred packaging was not validated as reliably as the tested virtual-environment launcher.

