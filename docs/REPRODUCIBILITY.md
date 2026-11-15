# Reproducibility

The public model metadata records feature order, target definition, training count, software versions, validation metrics, source-table checksum, and model checksum. The model file stores the full preprocessing and estimator Pipeline.

The private retraining command used for the release is:

```bat
python scripts\train_model.py --feature-table <verified-feature-table.csv> --orca-dir <vacuum-frequency-out-directory> --output models --results validation_results
```

Raw ORCA calculations and the complete training table are not redistributed. The parser can independently extract the final electronic energy, ZPE, total thermal energy, enthalpy, Gibbs energy, frequencies, imaginary-frequency count, and normal-termination state from authorized local outputs.

