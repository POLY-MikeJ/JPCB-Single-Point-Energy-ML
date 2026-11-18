# Bundled xTB runtime validation — v1.4.0

Validation date: 2026-11-18 (Asia/Shanghai)  
Platform: Windows 11 x64  
Branch: `fix/v1.4.0-bundled-xtb-runtime`

## Root cause and repair

The desktop shortcut launched an isolated installation that contained neither `runtime/xtb/xtb.exe` nor an inherited xTB environment variable. The prior detector checked an explicit path, `PATH`, and development-only `local_tools`, so the UI correctly reported xTB unavailable even though a separate development copy existed elsewhere.

The repaired discovery order is:

1. Installer-owned `runtime/xtb/xtb.exe`.
2. Verified explicit/per-user saved path and documented `XTB_EXE` override.
3. `PATH`.
4. Paths declared in `config/xtb_locations.json` or untracked `config/xtb_locations.local.json`.

Every candidate must execute `xtb.exe --version` successfully and identify itself as xTB. The launcher exports `ZHU_MOLENERGY_ROOT`, `XTB_EXE`, `XTBPATH`, and a private DLL search path to its Streamlit child. The calculation subprocess independently constructs the same isolated environment.

## Runtime provenance and redistribution record

- Upstream: official `grimme-lab/xtb` v6.7.1 release.
- Binary: `xtb-6.7.1pre-windows-x86_64.zip`.
- Upstream archive SHA-256: `043e578da4a7e114a4d584972959a875e3ffb9f2767a86723b95aa6719d28d9c`.
- `xtb.exe` SHA-256: `90bff4e570ffa10a1558364ee393711900bff239f02d313685353e055324f4c3`.
- `libiomp5md.dll` SHA-256: `8a90e1e81634eae33d65d34a1bc9e02a8f424df2f3ef203069c4f2e632e6fe65`.
- Version output: `xtb version 6.7.1pre (5071a88)`, compiled 2024-07-23.
- xTB license: LGPL-3.0-or-later. The installer includes `COPYING`, `COPYING.LESSER`, the exact v6.7.1 corresponding-source archive, URLs, and file hashes.
- The Intel OpenMP DLL is retained unmodified from the official upstream Windows archive. Intel documents the OpenMP runtime as redistributable and documents private deployment of required runtime DLLs; the package retains provenance and does not use Intel names for endorsement.

## Required charged-molecule calculation

Input: `CC[N+](C)(C)CCO`; formal charge `+1`; unpaired electrons `0`; GFN2-xTB; gas phase; optimization level `normal`; one thread.

| Result | Value |
|---|---:|
| Exit code | 0 |
| Geometry converged | Yes |
| Optimization cycles | 33 |
| Final SCC iterations | 3 |
| Initial energy | -27.575929200 Eh |
| Final energy | -27.586435088857 Eh |
| Energy change | -0.010505888857 Eh |
| HOMO | -15.3923 eV |
| LUMO | -6.3846 eV |
| HOMO–LUMO gap | 9.007728608370 eV |
| Dipole magnitude | 1.354 D |
| Final gradient norm | 0.000433467118 Eh/bohr |
| Atomic partial charges | 24 values |
| Wiberg bond orders | 23 records |

The optimized XYZ, JSON, CSV, HTML, TXT, SDF, MOL, raw log, SHA-256 manifest, and complete-job ZIP were generated. Missing values remain JSON `null` and display as `Not reported by this calculation`; no electronic property is inferred.

## Independent installer and desktop validation

The installer ZIP was extracted into a new directory without an existing `.venv`. Offline setup used the bundled Python 3.13.5 bootstrap and 59-wheel wheelhouse, with no Anaconda and no network dependency download. `setup_report.json` recorded six official models, the reference prediction `-244.906205123382 Eh`, and `bundled runtime` xTB discovery.

The installed desktop shortcut was launched. Streamlit listened on port 8501, returned HTTP 200, and launcher state recorded the bundled executable and parameter path. A Streamlit AppTest interaction selected Molecular Explorer and pressed **Optimize with GFN2-xTB** using the required inputs. It returned all three energy metrics, no UI error/exception, and 11 download controls. Clean shutdown removed the launcher-owned process and listener.

One deliberately deep extraction path reproduced Windows `MAX_PATH` error 206 while unpacking setuptools. A shorter independent installation path passed. Users should extract the installer near a drive root unless system long-path support is enabled.

## Regression and integrity

- Local suite: 52 passed, 0 failed, 0 skipped.
- Six official model hashes match their immutable metadata.
- No model, original DFT dataset, or raw ORCA source was modified.
- The public source repository does not track the 59 MB xTB executable. `scripts/stage_xtb_runtime.py` admits only the pinned official archive and constructs the installer runtime reproducibly.
