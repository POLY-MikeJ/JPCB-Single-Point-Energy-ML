# ZHU MolEnergy Workbench v1.2.1 development features

## Desktop launch

`Launch_ZHU_MolEnergy.bat` uses the project `.venv` directly and binds to localhost. `Install_ZHU_MolEnergy_Desktop_Shortcut.bat` creates the **ZHU MolEnergy Workbench** per-user shortcut without administrator rights. `Stop_ZHU_MolEnergy.bat` reads launcher state and targets only its recorded PID. The JPCB-named scripts remain compatibility aliases.

## Molecular viewers

2D rendering is based on RDKit and preserves the parsed chemical graph while changing display settings. 3D conformers are seeded ETKDG geometries with optional MMFF94, MMFF94s, or UFF optimization. They are not the published ORCA geometries. RMSD is computed only after exact atom-order and element checks.

## GFN2-xTB adapter

xTB is detected from an explicit executable path or PATH and verified with `--version`. It is not bundled. Jobs run in unique directories beneath `local_jobs/xtb`, with charge and number of unpaired electrons recorded separately. Optional ALPB solvents are restricted to the adapter's supported list. GFN2-xTB energy and geometry are never labeled as DFT or substituted for the ORCA-trained target.

## Scientific QC governance

The local audit preserves all source data. A composition reference is fitted out-of-fold by canonical structure group. Its robust residual is a review signal rather than an exclusion rule. `review_decisions.csv` supports explicit include, exclude, and restore decisions without editing raw files. Detailed paths and record-level findings stay outside the public Git tree.
