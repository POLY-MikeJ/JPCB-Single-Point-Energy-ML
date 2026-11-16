# Model card

## Versioning

The root `gpr_model.joblib` is the immutable v1.0.0 209-record vacuum reference. Version 1.1.0 adds five independent models under `models/v1.1.0`, each trained on the same 207 protocol-consistent records. `HEA` and `HEMA` are excluded only from the enhanced paired models because their water outputs did not execute CPCM. Every enhanced artifact is a complete Pipeline plus an applicability profile and has its own SHA-256 metadata.

## Intended use

Rapid local screening and ranking of the electronic single-point energy of curated, closed-shell, polar or charged polymerizable monomers.

## Target

Final ORCA `FINAL SINGLE POINT ENERGY` from vacuum B3LYP/6-311++G(d,p) frequency calculations at optimized geometries, in Eh. The release model is retrained directly from the current raw ORCA electronic energies and does not include ZPE or thermal corrections. A historical target table differs from some current raw outputs; this does not enter the fitted release labels and is documented in the private review package.

## Training and evaluation

The artifact is a median-imputer → StandardScaler → GaussianProcessRegressor Pipeline. The GPR kernel starts as Constant × RBF + WhiteKernel, with `alpha=1e-6`, `normalize_y=True`, seed 42, a fixed 80/20 split, and shuffled five-fold CV. It is trained on 209 records matched one-to-one by molecule name to the paper's local ORCA frequency outputs. Machine-readable actual metrics are in `models/model_metadata.json`.

Enhanced models additionally report a canonical-isomeric-SMILES `GroupShuffleSplit` holdout and `GroupKFold` cross-validation, using the same group split across solvents. Their deployment artifacts are fitted to all 207 eligible records after evaluation. The 791 water calculations are an additional external evaluation set, not an independent test: four canonical structures overlap the core set and independent selection provenance is not established.

Applicability status combines strict and robust descriptor-range checks with standardized nearest-neighbor distance. Borderline and outside thresholds are fitted from training-only leave-one-out nearest-neighbor distances and recorded in metadata. These flags are diagnostics rather than calibrated accuracy guarantees.

## Limitations

Absolute electronic energy is strongly size- and composition-dependent. Do not interpret cross-composition rankings as thermodynamic reaction energies. Exclude metals, radicals, zwitterions, ion pairs, oligomers, and extrapolative chemistry unless validated independently. The model does not replace conformer searches, geometry optimization, frequency analysis, or electronic-structure calculations.

