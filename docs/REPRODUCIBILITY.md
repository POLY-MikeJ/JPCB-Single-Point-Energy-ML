# Reproducibility

The public model metadata records feature order, target definition, training count, software versions, validation metrics, source-table checksum, and model checksum. The model file stores the full preprocessing and estimator Pipeline.

The v1.1 artifacts preserve the v1.0.0 SHA-256 and add environment-specific metadata, parsed dielectric constants, shared group-aware validation, protocol exclusions, and applicability thresholds.

The private retraining command used for the release is:

```bat
python scripts\train_model.py --feature-table <verified-feature-table.csv> --orca-dir <vacuum-frequency-out-directory> --output models --results validation_results
```

Raw ORCA calculations and the complete training table are not redistributed. The parser can independently extract the final electronic energy, ZPE, total thermal energy, enthalpy, Gibbs energy, frequencies, imaginary-frequency count, and normal-termination state from authorized local outputs.

Multi-solvent retraining uses `scripts/train_multisolvent.py` with explicit local paths for calculation data, the verified core feature table, monomer identities, and the candidate library. The script requires exact file-stem mappings, confirms normal termination, audits environment protocols, uses one shared canonical-structure split, writes prediction-level results, and records model hashes.

