# Data dictionary

| Field | Meaning |
|---|---|
| `smiles` | Input molecular structure |
| `canonical_smiles` | RDKit canonicalized structure |
| `predicted_E_sp_Eh` | Predicted electronic single-point energy, Eh |
| `predictive_std_Eh` | GPR predictive standard deviation, Eh; not calibrated |
| `status` | `ok` or `error` |
| `error` | Per-row diagnostic text |
| `duplicate_input` | Repeated input text within the batch |

Version 1.1 additionally exports `applicability_status`, `applicability_reasons`, `nearest_neighbor_distance`, `nearest_training_record_id`, `nearest_training_name`, `out_of_range_features`, `robust_out_of_range_features`, and all eight prefixed model descriptors. `duplicate_canonical` identifies repeated standardized structures rather than repeated raw text.

The model feature order is: `ATS0m`, `ZMIC2`, `ATSC0p`, `ATS2s`, `VR2_D`, `AETA_eta_R`, `ETA_eta_F`, `ATSC0dv`, each stored with a `mordred_` prefix.

