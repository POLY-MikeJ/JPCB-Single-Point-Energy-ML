"""Single and batch prediction services."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from .descriptors import FEATURES, calculate_descriptors
from .model import load_model


def predict_one(smiles: str, model_dir: str | Path) -> dict:
    model, metadata = load_model(model_dir)
    canonical, descriptors = calculate_descriptors(smiles)
    frame = pd.DataFrame([[descriptors[f] for f in FEATURES]], columns=FEATURES)
    mean, std = model.predict(frame, return_std=True)
    return {
        "input_smiles": smiles,
        "canonical_smiles": canonical,
        "prediction": float(mean[0]),
        "predictive_std": float(std[0]),
        "unit": metadata["target_unit"],
        "model_version": metadata["model_version"],
        "descriptors": descriptors,
        "applicability_note": metadata["applicability_domain"],
    }


def predict_batch(table: pd.DataFrame, model_dir: str | Path) -> pd.DataFrame:
    if "smiles" not in table.columns:
        raise ValueError("Input CSV must contain a 'smiles' column")
    output = table.copy()
    records = []
    cache: dict[str, dict] = {}
    for _, row in output.iterrows():
        raw = row.get("smiles")
        key = "" if pd.isna(raw) else str(raw).strip()
        if key in cache:
            result = dict(cache[key])
            result["duplicate_input"] = True
        else:
            try:
                pred = predict_one(key, model_dir)
                result = {
                    "canonical_smiles": pred["canonical_smiles"],
                    "predicted_E_sp_Eh": pred["prediction"],
                    "predictive_std_Eh": pred["predictive_std"],
                    "status": "ok",
                    "error": "",
                    "duplicate_input": False,
                }
            except Exception as exc:
                result = {
                    "canonical_smiles": "",
                    "predicted_E_sp_Eh": np.nan,
                    "predictive_std_Eh": np.nan,
                    "status": "error",
                    "error": str(exc),
                    "duplicate_input": False,
                }
            cache[key] = dict(result)
        records.append(result)
    return pd.concat([output.reset_index(drop=True), pd.DataFrame(records)], axis=1)

