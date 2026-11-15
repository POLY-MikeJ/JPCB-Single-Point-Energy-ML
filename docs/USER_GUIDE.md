# User guide

For one molecule, paste a valid SMILES string in the **Single molecule** tab and select **Predict**. Review the canonical SMILES, 2D structure, `E_sp` in Eh, predictive standard deviation, and descriptor values.

For batch inference, upload a UTF-8 CSV with a `smiles` column. Optional identifiers and all other columns are retained. Download the result after processing. `status=error` rows contain a diagnostic message; valid rows still complete. `duplicate_input=true` indicates that the same input text was already evaluated in the batch.

Predictions outside the applicability domain require independent ORCA validation. The reported standard deviation is a GPR predictive standard deviation, not a calibrated confidence interval.

