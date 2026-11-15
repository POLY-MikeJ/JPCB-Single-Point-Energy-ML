# JPCB Single-Point Energy ML

Windows-ready local software for predicting the ORCA single-point electronic energy (`E_sp`) of polar and charged polymer monomers with the eight-descriptor Gaussian process regression workflow reported in:

> Jie Zhu, Jing Zhou, Zhaoyan Sun, Xiayun Huang, and Zhihong Nie, “High-Throughput Prediction of Single-Point Energies for Charged Polymer Monomers through Feature-Engineered Machine Learning,” *The Journal of Physical Chemistry B* (2026). [Article DOI](https://doi.org/10.1021/acs.jpcb.6c02936) · [Supporting Information DOI](https://doi.org/10.1021/acs.jpcb.6c02936.s001)

## Scope

The released model uses Mordred descriptors `ATS0m`, `ZMIC2`, `ATSC0p`, `ATS2s`, `VR2_D`, `AETA_eta_R`, `ETA_eta_F`, and `ATSC0dv`. The saved artifact is a complete scikit-learn Pipeline containing median imputation, standardization, and GPR. Input is processed locally; no molecular data are uploaded.

The verified software target is the final ORCA electronic SCF energy printed as `FINAL SINGLE POINT ENERGY` by the vacuum frequency calculation at the optimized geometry, in Hartree (`Eh`). Thermal energy, enthalpy, and Gibbs energy are separately parsed and are not the released model target.

## Windows installation and GUI

Install 64-bit Python 3.10-3.13 from [python.org](https://www.python.org/downloads/windows/) and select **Add Python to PATH**. Then double-click:

1. `install_windows.bat`
2. `run_windows.bat`

The Streamlit interface provides single-molecule prediction, a 2D structure, descriptor inspection, and fault-tolerant batch CSV prediction.

## Command line

```bat
.venv\Scripts\python.exe scripts\predict.py "C=CC(=O)N"
.venv\Scripts\python.exe scripts\batch_predict.py examples\example_molecules.csv predictions.csv
.venv\Scripts\python.exe scripts\parse_orca.py calculation.out parsed.csv
```

Batch input must contain a `smiles` column. Other columns are preserved. Invalid rows receive an error message without stopping the batch, and repeated inputs are marked.

## Model and applicability

The model was retrained directly on the current raw electronic energies of 209 records with a one-to-one match to the paper's local vacuum-frequency ORCA files, using an 80/20 split, random seed 42, and five-fold shuffled cross-validation. Actual validation metrics are stored in `models/model_metadata.json`. GPR predictive standard deviation is exposed as a model output but is not a calibrated confidence interval.

Use the model as a screening and ranking tool for curated, closed-shell, polar or charged polymerizable monomers within the training descriptor space. Independently validate metals, radicals, zwitterions, explicit ion pairs, oligomers, highly flexible fragments, and extrapolative structures with quantum chemistry.

## Reproducibility and tests

See [Reproducibility](docs/REPRODUCIBILITY.md), [Model card](docs/MODEL_CARD.md), [Data dictionary](docs/DATA_DICTIONARY.md), and [Windows guide](docs/INSTALL_WINDOWS.md). Run:

```bat
.venv\Scripts\python.exe -m pytest -q
```

## Data and licensing

Source code is MIT licensed. No license for the underlying research data is granted by the MIT code license. The repository includes only small input/output examples and model metadata; complete raw ORCA outputs and unpublished molecular libraries are not distributed.

