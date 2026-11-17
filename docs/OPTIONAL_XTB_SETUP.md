# Optional native Windows xTB setup

xTB is not included in the ZHU MolEnergy installer. Obtain a native Windows x64 build from the official xTB project or an authorized distributor and follow its license and citation instructions. In **Molecular Explorer → Geometry optimization**, enter the full path to `xtb.exe`. The Workbench runs `xtb.exe --version` before enabling calculation.

The validated owner environment used xTB 6.7.1pre (commit 5071a88). Other versions may emit different optional fields; unknown lines remain in the downloadable raw log and unavailable structured fields are never inferred. Run a small molecule first and inspect the complete job ZIP. WSL builds are not invoked by the Windows application.
