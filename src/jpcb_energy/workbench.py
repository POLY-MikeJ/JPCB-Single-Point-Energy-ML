"""High-throughput prediction with official model bundles."""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

from .applicability import assess_domain
from .descriptors import FEATURES, calculate_descriptors


def predict_with_bundle(smiles: str, model_entry: dict) -> dict:
    canonical, descriptors = calculate_descriptors(smiles)
    X = pd.DataFrame([[descriptors[f] for f in FEATURES]], columns=FEATURES)
    mean, std = model_entry["pipeline"].predict(X, return_std=True)
    domain = assess_domain(descriptors, model_entry["domain_profile"], canonical) if model_entry.get("domain_profile") else {
        "applicability_status": "not_available_for_legacy_model",
        "applicability_reasons": ["v1.0.0 metadata predates the v1.1.0 domain profile"],
        "nearest_neighbor_distance": np.nan,
        "nearest_training_record_id": "",
        "nearest_training_name": "",
        "out_of_range_features": [],
        "robust_out_of_range_features": [],
    }
    return {"canonical_smiles": canonical, "prediction": float(mean[0]), "predictive_std": float(std[0]), "descriptors": descriptors, **domain}


def batch_predict(table: pd.DataFrame, model_entry: dict, chunk_size: int = 500) -> tuple[pd.DataFrame, dict]:
    """Featurize once per canonical structure and predict in vectorized chunks."""
    if "smiles" not in table.columns:
        raise ValueError("Input table must contain a 'smiles' column")
    started = time.perf_counter()
    rows, canonical_cache, unique = [], {}, {}
    for position, raw in enumerate(table["smiles"]):
        text = "" if pd.isna(raw) else str(raw).strip()
        try:
            canonical, desc = calculate_descriptors(text)
            duplicate = canonical in unique
            unique.setdefault(canonical, desc)
            rows.append({"_canonical": canonical, "status": "ok", "error": "", "duplicate_canonical": duplicate})
        except Exception as exc:
            rows.append({"_canonical": "", "status": "error", "error": str(exc), "duplicate_canonical": False})
    valid_keys = list(unique)
    predictions = {}
    for start in range(0, len(valid_keys), max(1, chunk_size)):
        keys = valid_keys[start:start + chunk_size]
        X = pd.DataFrame([[unique[k][f] for f in FEATURES] for k in keys], columns=FEATURES)
        mean, std = model_entry["pipeline"].predict(X, return_std=True)
        for key, m, s in zip(keys, mean, std):
            domain = assess_domain(unique[key], model_entry["domain_profile"], key) if model_entry.get("domain_profile") else {"applicability_status": "not_available_for_legacy_model", "applicability_reasons": [], "nearest_neighbor_distance": np.nan, "nearest_training_record_id": "", "nearest_training_name": "", "out_of_range_features": [], "robust_out_of_range_features": []}
            predictions[key] = {"predicted_E_sp_Eh": float(m), "predictive_std_Eh": float(s), **domain, **unique[key]}
    diagnostics = []
    for row in rows:
        item = dict(row)
        key = item.pop("_canonical")
        item["canonical_smiles"] = key
        if key:
            item.update(predictions[key])
        diagnostics.append(item)
    result = pd.concat([table.reset_index(drop=True), pd.DataFrame(diagnostics)], axis=1)
    summary = {
        "input_records": len(table),
        "valid_records": int((result.status == "ok").sum()),
        "invalid_records": int((result.status == "error").sum()),
        "unique_valid_structures": len(valid_keys),
        "duplicate_records": int(result.duplicate_canonical.sum()),
        "within_domain": int((result.get("applicability_status") == "within_domain").sum()),
        "borderline": int((result.get("applicability_status") == "borderline").sum()),
        "outside_domain": int((result.get("applicability_status") == "outside_domain").sum()),
        "elapsed_seconds": time.perf_counter() - started,
    }
    return result, summary
