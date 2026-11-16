# JPCB Energy Workbench

Windows-ready, local molecular energy prediction and ORCA analysis software for polar and charged polymer monomers. Version 1.1 extends the published-reference workflow while preserving the exact v1.0.0 vacuum model.

> Jie Zhu, Jing Zhou, Zhaoyan Sun, Xiayun Huang, and Zhihong Nie, “High-Throughput Prediction of Single-Point Energies for Charged Polymer Monomers through Feature-Engineered Machine Learning,” *The Journal of Physical Chemistry B* (2026). [Article DOI](https://doi.org/10.1021/acs.jpcb.6c02936) · [Supporting Information DOI](https://doi.org/10.1021/acs.jpcb.6c02936.s001)

## Workbench scope

The official models use Mordred descriptors `ATS0m`, `ZMIC2`, `ATSC0p`, `ATS2s`, `VR2_D`, `AETA_eta_R`, `ETA_eta_F`, and `ATSC0dv`. The application provides:

- single-molecule and high-throughput prediction;
- vacuum, ethanol, DMSO, water, and formamide models;
- descriptor-range and nearest-neighbor applicability diagnostics;
- 2D structure export and seeded illustrative 3D conformers;
- model-input and exploratory descriptor tables;
- recursive, read-only ORCA output indexing;
- isolated group-aware user-model training.

All molecular processing remains local. The target is the final ORCA electronic SCF energy printed as `FINAL SINGLE POINT ENERGY` by the environment-specific frequency calculation at its optimized geometry, in Hartree (`Eh`). ZPE, thermal energy, enthalpy, and Gibbs energy are separately parsed and are not mixed with this target.

## Official model registry

- `v1.0.0-vacuum-reference`: immutable published-reference artifact at `models/gpr_model.joblib`.
- `v1.1.0-gpr-vacuum`, `-ethanol`, `-dmso`, `-water`, and `-formamide`: independent complete GPR Pipelines under `models/v1.1.0/`.

The enhanced comparison uses 207 protocol-consistent molecules in every environment. `HEA` and `HEMA` were excluded from all five enhanced models because their water output files did not execute CPCM, although the separate input files requested it. The original 209-record v1.0.0 model is unchanged. Model metadata records the ORCA-output dielectric constants: vacuum 1.0, ethanol 25.451, DMSO 47.381, water 80.151, and formamide 110.986.

## Windows installation and GUI

Install 64-bit Python 3.10-3.13 from [python.org](https://www.python.org/downloads/windows/) and select **Add Python to PATH**. Double-click `install_windows.bat`, then `run_windows.bat`. No Anaconda installation or GPU is required.

The desktop-style interface has seven workspaces: Predict, Batch Screening, Molecular Explorer, Solvent Comparison, ORCA Workbench, Model Training, and Model & Documentation.

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

See [Reproducibility](docs/REPRODUCIBILITY.md), [Model card](docs/MODEL_CARD.md), [Data dictionary](docs/DATA_DICTIONARY.md), [Workbench guide](docs/WORKBENCH_V1.1.md), and [Windows guide](docs/INSTALL_WINDOWS.md).

```bat
.venv\Scripts\python.exe -m pytest -q
```

## Data and licensing

Source code is MIT licensed. No license for underlying research data is granted by the MIT code license. Complete raw ORCA outputs, private training tables, and unpublished libraries are not distributed.
