# Bundled and optional native Windows xTB setup

xTB 6.7.1pre is included in the ZHU MolEnergy Windows installer under `runtime/xtb`, together with its parameter files, licenses, corresponding source, provenance, and checksums. It is detected and verified automatically. Advanced users may instead select another native Windows x64 `xtb.exe` in **Molecular Explorer → Geometry optimization** and save that verified choice in the per-user configuration. The Workbench runs `xtb.exe --version` before enabling calculation.

The bundled, validated runtime is xTB 6.7.1pre (commit 5071a88). Other user-selected versions may emit different optional fields; unknown lines remain in the downloadable raw log and unavailable structured fields are never inferred. Run a small molecule first and inspect the complete job ZIP. WSL builds are not invoked by the Windows application.
