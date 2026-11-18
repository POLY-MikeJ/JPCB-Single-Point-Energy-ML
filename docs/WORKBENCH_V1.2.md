# ZHU MolEnergy Workbench v1.3.0 development features

## Desktop launch

`Start_ZHU_MolEnergy.bat` validates the existing project `.venv`, performs a Streamlit application-render preflight, selects a free localhost port and opens the browser. `Install_ZHU_MolEnergy_Desktop_Shortcut.bat` creates the **ZHU MolEnergy Workbench** per-user shortcut without administrator rights. `Stop_ZHU_MolEnergy.bat` reads launcher state and targets only its recorded PID. `Launch_ZHU_MolEnergy.bat` and the JPCB-named scripts remain compatibility aliases.

## Molecular viewers

2D rendering is based on RDKit and preserves the parsed chemical graph while changing display settings. Publication, index, charge, heteroatom, aromatic and transparent-background modes are supported. 3D conformers are seeded ETKDG geometries with optional MMFF94, MMFF94s, or UFF optimization and six display representations. They are not the published ORCA geometries. RMSD is computed only after exact atom-order and element checks.

## GFN2-xTB adapter

xTB is discovered from the bundled installer runtime, a saved user selection, PATH, or administrator configuration, and every candidate is verified with `--version`. Jobs run in unique directories beneath `local_jobs/xtb`, with charge and number of unpaired electrons recorded separately. Optional ALPB solvents are restricted to the adapter's supported list. GFN2-xTB energy and geometry are never labeled as DFT or substituted for the ORCA-trained target.

## Scientific QC governance

The local audit preserves all source data. A composition reference is fitted out-of-fold by canonical structure group. Its robust residual is a review signal rather than an exclusion rule. `review_decisions.csv` supports explicit include, exclude, and restore decisions without editing raw files. Detailed paths and record-level findings stay outside the public Git tree.

The reversible Data Cleaning workspace combines IQR, Z-score, modified Z-score/MAD, Isolation Forest, composition-adjusted residuals and ORCA-QC evidence. Category A records may be suggested for exclusion from a working copy; category B statistical extremes are retained until a user explicitly selects an action. Undo, Restore Original Dataset, and three provenance-bearing output files protect the original audit and raw calculations.
