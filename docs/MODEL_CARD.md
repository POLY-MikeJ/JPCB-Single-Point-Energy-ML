# Model card

## Intended use

Rapid local screening and ranking of the electronic single-point energy of curated, closed-shell, polar or charged polymerizable monomers.

## Target

Final ORCA `FINAL SINGLE POINT ENERGY` from vacuum B3LYP/6-311++G(d,p) frequency calculations at optimized geometries, in Eh. The release model is retrained directly from the current raw ORCA electronic energies and does not include ZPE or thermal corrections. A historical target table differs from some current raw outputs; this does not enter the fitted release labels and is documented in the private review package.

## Training and evaluation

The artifact is a median-imputer → StandardScaler → GaussianProcessRegressor Pipeline. The GPR kernel starts as Constant × RBF + WhiteKernel, with `alpha=1e-6`, `normalize_y=True`, seed 42, a fixed 80/20 split, and shuffled five-fold CV. It is trained on 209 records matched one-to-one by molecule name to the paper's local ORCA frequency outputs. Machine-readable actual metrics are in `models/model_metadata.json`.

## Limitations

Absolute electronic energy is strongly size- and composition-dependent. Do not interpret cross-composition rankings as thermodynamic reaction energies. Exclude metals, radicals, zwitterions, ion pairs, oligomers, and extrapolative chemistry unless validated independently. The model does not replace conformer searches, geometry optimization, frequency analysis, or electronic-structure calculations.

