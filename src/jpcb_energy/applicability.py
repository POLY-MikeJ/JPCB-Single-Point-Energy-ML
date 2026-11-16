"""Training-distribution applicability-domain diagnostics."""

from __future__ import annotations

import numpy as np

from .descriptors import FEATURES, molecular_warnings


def build_domain_profile(X, record_ids, names) -> dict:
    values = np.asarray(X, dtype=float)
    mean = values.mean(axis=0)
    scale = values.std(axis=0)
    scale[scale == 0] = 1.0
    z = (values - mean) / scale
    nearest = []
    for i in range(len(z)):
        d = np.linalg.norm(z[i] - z, axis=1)
        d[i] = np.inf
        nearest.append(float(np.min(d)))
    return {
        "features": FEATURES,
        "mean": mean.tolist(),
        "scale": scale.tolist(),
        "min": values.min(axis=0).tolist(),
        "max": values.max(axis=0).tolist(),
        "q01": np.quantile(values, 0.01, axis=0).tolist(),
        "q99": np.quantile(values, 0.99, axis=0).tolist(),
        "training_X": values.tolist(),
        "record_ids": list(record_ids),
        "names": list(names),
        "distance_borderline": float(np.quantile(nearest, 0.95)),
        "distance_outside": float(np.quantile(nearest, 0.99) * 1.5),
        "threshold_protocol": "95th and 1.5x-99th percentiles of leave-one-out standardized nearest-neighbor distances on training-only data",
    }


def assess_domain(descriptor_values: dict[str, float], profile: dict, smiles: str = "") -> dict:
    x = np.array([descriptor_values[f] for f in profile["features"]], dtype=float)
    training = np.asarray(profile["training_X"], dtype=float)
    mean, scale = np.asarray(profile["mean"]), np.asarray(profile["scale"])
    distances = np.linalg.norm((training - x) / scale, axis=1)
    nearest_index = int(np.argmin(distances))
    nearest_distance = float(distances[nearest_index])
    strict = [f for f, v, lo, hi in zip(profile["features"], x, profile["min"], profile["max"]) if v < lo or v > hi]
    robust = [f for f, v, lo, hi in zip(profile["features"], x, profile["q01"], profile["q99"]) if v < lo or v > hi]
    chemistry = molecular_warnings(smiles) if smiles else []
    reasons = []
    if strict:
        reasons.append("descriptor(s) outside training minimum/maximum")
    elif robust:
        reasons.append("descriptor(s) outside training 1st-99th percentile range")
    if nearest_distance > profile["distance_outside"]:
        reasons.append("standardized nearest-neighbor distance exceeds outside-domain threshold")
    elif nearest_distance > profile["distance_borderline"]:
        reasons.append("standardized nearest-neighbor distance exceeds borderline threshold")
    reasons.extend(chemistry)
    if strict or chemistry or nearest_distance > profile["distance_outside"]:
        status = "outside_domain"
    elif robust or nearest_distance > profile["distance_borderline"]:
        status = "borderline"
    else:
        status = "within_domain"
    return {
        "applicability_status": status,
        "applicability_reasons": reasons,
        "nearest_neighbor_distance": nearest_distance,
        "nearest_training_record_id": profile["record_ids"][nearest_index],
        "nearest_training_name": profile["names"][nearest_index],
        "out_of_range_features": strict,
        "robust_out_of_range_features": robust,
    }
