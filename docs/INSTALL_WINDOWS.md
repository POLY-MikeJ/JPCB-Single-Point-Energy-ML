# Windows installation

Use 64-bit Windows 10 or 11 and Python 3.10-3.13. Download Python from python.org and enable **Add Python to PATH**. Double-click `install_windows.bat`; it checks the Python version, creates project-local `.venv`, installs pinned CPU dependencies, and installs the package. Double-click `run_windows.bat` to open the local application. Paths containing spaces and non-ASCII characters are supported.

For offline use, run `prepare_offline_windows.ps1` on a connected computer with the same Python minor version. Copy the generated `wheelhouse` with the repository and run `install_windows_offline.bat`. No runtime CDN or cloud service is required. PyInstaller is not used because RDKit/Mordred packaging was not validated as reliably as the tested virtual-environment launcher.

