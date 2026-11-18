# ZHU MolEnergy Workbench

*Molecular Energy Prediction, Visualization & Computational Chemistry*

Windows-ready local software for molecular-energy prediction, molecular visualization, geometry optimization, ORCA analysis, and traceable DFT quality control. Version 1.4.0 adds complete xTB job records and a verified offline Windows installer while preserving every v1.0.0/v1.1.0 model identifier and artifact.

> Jie Zhu, Jing Zhou, Zhaoyan Sun, Xiayun Huang, and Zhihong Nie. **High-Throughput Prediction of Single-Point Energies for Charged Polymer Monomers through Feature-Engineered Machine Learning.** *The Journal of Physical Chemistry B* **2026**, **130** (22), 5819–5828. [Article DOI](https://doi.org/10.1021/acs.jpcb.6c02936) · [Supporting Information DOI](https://doi.org/10.1021/acs.jpcb.6c02936.s001)

## Reference & Citation

ZHU MolEnergy Workbench is built on the scientific research and pretrained molecular-energy models reported in the JPCB article above. If you use its published method or pretrained models, cite:

> Zhu, J.; Zhou, J.; Sun, Z.; Huang, X.; Nie, Z. High-Throughput Prediction of Single-Point Energies for Charged Polymer Monomers through Feature-Engineered Machine Learning. *J. Phys. Chem. B* **2026**, **130** (22), 5819–5828. https://doi.org/10.1021/acs.jpcb.6c02936.

Machine-readable records are provided in [`CITATION.cff`](CITATION.cff) and [`CITATION.bib`](CITATION.bib). GFN2-xTB optimization, interactive 3D rendering, expanded solvent workbench features, and database-QC tooling are subsequent software extensions; they are not described as original results of the JPCB paper.

The proposed future repository slug is `POLY-MikeJ/ZHU-MolEnergy`. The repository itself is not renamed by this development branch; a repository-owner rename and redirect verification remain a separate approved release action.

## Workbench scope

The official models use Mordred descriptors `ATS0m`, `ZMIC2`, `ATSC0p`, `ATS2s`, `VR2_D`, `AETA_eta_R`, `ETA_eta_F`, and `ATSC0dv`. The application provides:

- single-molecule and high-throughput prediction;
- vacuum, ethanol, DMSO, water, and formamide models;
- descriptor-range and nearest-neighbor applicability diagnostics;
- configurable 2D SVG/PNG rendering and seeded multi-conformer 3D exploration;
- optional, separately labeled local GFN2-xTB geometry optimization;
- reproducible, non-destructive DFT database quality control;
- model-input and exploratory descriptor tables;
- recursive, read-only ORCA output indexing;
- isolated group-aware user-model training.

All molecular processing remains local. The released model artifacts predict the final ORCA electronic SCF energy printed as `FINAL SINGLE POINT ENERGY` by the environment-specific frequency calculation at its optimized geometry, in Hartree (`Eh`). ZPE, thermal energy, enthalpy, and Gibbs energy are separately parsed and are not mixed with these released labels.

The published article contains an internal wording inconsistency: its introduction defines `E_sp` as final SCF electronic energy, while one Methods sentence says SCF energy combined with thermal corrections at 298.15 K. Direct inspection of the original `monomers_0404.csv` target column, raw ORCA outputs, training-validation table, and immutable released model metadata shows that the distributed model labels correspond to `FINAL SINGLE POINT ENERGY`, not the thermal-energy/enthalpy/Gibbs fields. The software preserves those labels and reports the inconsistency rather than silently redefining the model.

## Official model registry

- `v1.0.0-vacuum-reference`: immutable published-reference artifact at `models/gpr_model.joblib`.
- `v1.1.0-gpr-vacuum`, `-ethanol`, `-dmso`, `-water`, and `-formamide`: independent complete GPR Pipelines under `models/v1.1.0/`.

The enhanced comparison uses 207 protocol-consistent molecules in every environment. `HEA` and `HEMA` were excluded from all five enhanced models because their water output files did not execute CPCM, although the separate input files requested it. The original 209-record v1.0.0 model is unchanged. Model metadata records the ORCA-output dielectric constants: vacuum 1.0, ethanol 25.451, DMSO 47.381, water 80.151, and formamide 110.986.

## Windows installation and GUI

### v1.4.0 offline installer

The release ZIP includes the official signed CPython 3.13.5 x64 installer, a complete cp313 Windows wheelhouse, the checksum-verified official v1.0.0/v1.1.0 models, and a verified official xTB 6.7.1pre Windows runtime. Extract the ZIP and double-click `Setup_ZHU_MolEnergy.bat`; no Anaconda, global PATH change, network package installation, or separate xTB configuration is required. The bundled xTB executable is isolated under `runtime/xtb`, with upstream licenses, corresponding source, provenance, and checksums.

xTB discovery is deterministic: bundled `runtime/xtb/xtb.exe`, a verified per-user saved path, system `PATH`, then administrator-defined entries in `config/xtb_locations.json` or untracked `config/xtb_locations.local.json`. Every candidate must successfully execute `--version`; file existence alone is insufficient.

For the existing validated installation, double-click `Start_ZHU_MolEnergy.bat`; it validates and invokes the project `.venv` directly, performs an application-render preflight, chooses a free localhost port starting at 8501, opens the browser, and remains attached to the service without relying on `python` or `py` on PATH. To create a per-user desktop shortcut named **ZHU MolEnergy Workbench**, double-click `Install_ZHU_MolEnergy_Desktop_Shortcut.bat`. Pressing Ctrl+C or closing the shared launcher console stops the attached service; `Stop_ZHU_MolEnergy.bat` is the clean manual alternative and targets only the PID recorded by this launcher. `Launch_ZHU_MolEnergy.bat` and the previous JPCB-named batch files remain compatibility aliases.

For a clean installation, install 64-bit Python 3.10-3.13, double-click `install_windows.bat`, then use the launcher. The server binds to `127.0.0.1`, disables usage telemetry, reuses a healthy launcher-owned instance, and chooses a free local port if 8501 is occupied.

GFN2-xTB jobs preserve the exact input structures, complete raw log, native `xtbout.json`, charges, Wiberg bond orders, optimized structures, structured JSON/CSV, HTML summary, SHA-256 manifest, and a complete downloadable job ZIP. GFN2-xTB is a semiempirical tight-binding method and is reported separately from ORCA DFT and GPR predictions.

The interface has nine workspaces: Predict, Batch Screening, Molecular Explorer, Solvent Comparison, ORCA Workbench, Model Training, local-owner Data Quality, reversible Data Cleaning & Outlier Removal, and About & Citation.

## Visualization, xTB, and DFT QC

The Molecular Explorer supports drawing styles, atom indices/maps, charges, hydrogens, stereo wedges, SMARTS highlighting, dimensions, rotation, backgrounds, and high-resolution export. Its interactive offline 3D viewer provides representation, colors, labels, hydrogen, background, radius, bond, spin, camera, RMSD, and export controls. Display settings never modify molecular identity.

GFN2-xTB is bundled in the Windows installer as a verified, isolated native runtime. The workbench also supports a verified user-selected executable and runs `--gfn 2 --opt <level>` with explicit charge and unpaired-electron arguments in an isolated `local_jobs/xtb` directory. xTB/ALPB results remain distinct from ORCA CPCM reference calculations and GPR predictions. RDKit MMFF/UFF optimization remains available independently.

`scripts/run_dft_qc.py` audits supplied ORCA files read-only. It checks identity, composition, charge/multiplicity, task, method/basis, solvent protocol, pairing, convergence evidence, frequencies, geometry contacts, and group-fold composition-aware residuals. The Data Cleaning workspace adds IQR, Z-score, modified Z-score/MAD, Isolation Forest, composition-residual and ORCA-QC screening. Explicit actions remove records only from a reversible working copy, with Undo/Restore and `dataset_cleaned_v1.csv`, `excluded_records.csv`, and `cleaning_report.json` exports. Statistical extremes are review signals only. Raw files and published-reference records are never edited or deleted, and cleaned-model diagnostics are never presented as published JPCB results.

For offline deployment, run `prepare_offline_windows.ps1` on a connected Windows computer with the target Python version, copy the repository plus generated `wheelhouse`, and run `install_windows_offline.bat` on the offline computer.

## Command line

```bat
.venv\Scripts\python.exe scripts\predict_v11.py "C=CC(=O)N" --model-id v1.1.0-gpr-water
.venv\Scripts\python.exe scripts\batch_predict_v11.py examples\example_molecules.csv predictions.csv --model-id v1.1.0-gpr-water
.venv\Scripts\python.exe scripts\parse_orca.py calculation.out parsed.csv
```

Batch input must contain `smiles`; all original rows and columns are preserved. Invalid rows receive diagnostics without stopping the batch. Canonical duplicates are featurized once and return consistent predictions.

## Validation and applicability

Enhanced models use a shared `GroupShuffleSplit` holdout and `GroupKFold` cross-validation keyed by standardized canonical isomeric SMILES, so a structure group cannot cross folds. Random-split and group-aware metrics are stored separately. The 791-record water set has four exact canonical overlaps with the core set and unestablished selection independence; it is reported as an additional external evaluation set, not an independent test set.

Applicability diagnostics combine training descriptor ranges, robust 1st-99th percentile ranges, standardized nearest-neighbor distance, and chemistry warnings. These are screening diagnostics, not proof of prediction accuracy. GPR predictive standard deviation is not a calibrated confidence interval.

Absolute total electronic energy is strongly composition- and atom-count-dependent. Meaningful energetic comparisons require chemically comparable systems or a defined balanced reaction. Independently validate extrapolative predictions with quantum chemistry.

The Molecular Explorer's 3D geometry is generated with seeded RDKit ETKDGv3 and MMFF94, with an explicitly labeled UFF fallback. It is illustrative, not an ORCA-optimized geometry, and is not used by the graph-descriptor models.

## Reproducibility and tests

See [Reproducibility](docs/REPRODUCIBILITY.md), [Model card](docs/MODEL_CARD.md), [Data dictionary](docs/DATA_DICTIONARY.md), [v1.2 workbench guide](docs/WORKBENCH_V1.2.md), and [Windows guide](docs/INSTALL_WINDOWS.md).

```bat
.venv\Scripts\python.exe -m pytest -q
```

## Data and licensing

Source code is MIT licensed. No license for underlying research data is granted by the MIT code license. Complete raw ORCA outputs, private training tables, and unpublished libraries are not distributed.
