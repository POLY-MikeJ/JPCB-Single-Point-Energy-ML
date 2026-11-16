# Workbench v1.1 guide

## Prediction and screening

Select an official model ID before prediction. The result includes the electronic energy in Eh, raw GPR predictive standard deviation, model version, target definition, and applicability diagnostics. Batch inference loads one model, caches canonical structures, predicts in chunks, preserves source rows, and exports descriptors and diagnostics.

## Solvent models

Five independent GPR models use the same 207 protocol-consistent structures and eight fixed Mordred descriptors. Their shared group split allows paired comparison. Do not interpret absolute energies of different compositions as relative stability or reaction energy.

## Molecular Explorer

The 2D view supports atom indices, charge highlighting, SVG, and PNG. The interactive 3D view uses seed 42 with ETKDGv3, MMFF94 when available, and UFF as an explicit fallback. SDF and XYZ downloads contain this illustrative RDKit conformer, not an ORCA geometry.

## ORCA Workbench

Enter a local directory. The application recursively reads `.out` files without modifying them, detects encoding, and extracts task, method, basis, charge, multiplicity, solvent, dielectric constant, termination, energies, frequencies, source path, and SHA-256. CSV and JSON exports are available. Pairing is not inferred from loose substrings.

## User models

Upload a CSV with `smiles` and a numeric target. User artifacts are written only under `user_models/<timestamp>` and never replace official files. Evaluation uses a canonical-SMILES group holdout and GroupKFold. Training-set performance is not presented as generalization performance.
