"""Isolated group-aware user model training."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, GradientBoostingRegressor, RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, cross_val_predict
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVR

from .descriptors import FEATURES, calculate_descriptors
from .model import sha256


def _estimator(name: str):
    choices = {
        "GPR": GaussianProcessRegressor(kernel=ConstantKernel(1.0) * RBF(1.0) + WhiteKernel(1e-3), alpha=1e-6, normalize_y=True, random_state=42),
        "SVR": SVR(C=50.0, epsilon=0.01),
        "Random Forest": RandomForestRegressor(n_estimators=400, random_state=42, n_jobs=-1),
        "ExtraTrees": ExtraTreesRegressor(n_estimators=400, random_state=42, n_jobs=-1),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=500, learning_rate=0.05, max_depth=4, random_state=42),
        "Ridge": Ridge(alpha=1.0),
    }
    if name not in choices:
        raise ValueError(f"Unsupported model family: {name}")
    return choices[name]


def train_user_model(table: pd.DataFrame, target_column: str, unit: str, model_family: str, workspace: str | Path) -> tuple[Path, dict]:
    if "smiles" not in table or target_column not in table:
        raise ValueError("The table must contain smiles and the selected target column")
    records = []
    for i, row in table.iterrows():
        try:
            canonical, desc = calculate_descriptors(str(row.smiles))
            target = float(row[target_column])
            if np.isfinite(target):
                records.append({"source_row": int(i), "canonical_smiles": canonical, "target": target, **desc})
        except Exception:
            continue
    frame = pd.DataFrame(records)
    if len(frame) < 20 or frame.canonical_smiles.nunique() < 10:
        raise ValueError("At least 20 valid records and 10 unique canonical structures are required")
    X, y, groups = frame[FEATURES], frame.target, frame.canonical_smiles
    split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    train_idx, test_idx = next(split.split(X, y, groups))
    pipe = Pipeline([("imputer", SimpleImputer(strategy="median")), ("scaler", StandardScaler()), ("model", _estimator(model_family))])
    pipe.fit(X.iloc[train_idx], y.iloc[train_idx])
    pred = pipe.predict(X.iloc[test_idx])
    folds = min(5, groups.nunique())
    cv = GroupKFold(folds)
    cv_pred = cross_val_predict(pipe, X, y, groups=groups, cv=cv)
    metrics = {
        "n_records": len(frame), "n_unique_groups": int(groups.nunique()), "group_overlap": len(set(groups.iloc[train_idx]) & set(groups.iloc[test_idx])),
        "holdout_mae": float(mean_absolute_error(y.iloc[test_idx], pred)), "holdout_rmse": float(mean_squared_error(y.iloc[test_idx], pred) ** 0.5), "holdout_r2": float(r2_score(y.iloc[test_idx], pred)),
        "group_cv_mae": float(mean_absolute_error(y, cv_pred)), "group_cv_rmse": float(mean_squared_error(y, cv_pred) ** 0.5), "group_cv_r2": float(r2_score(y, cv_pred)),
    }
    pipe.fit(X, y)
    root = Path(workspace).resolve()
    official = (Path(__file__).resolve().parents[2] / "models").resolve()
    if root == official or official in root.parents:
        raise ValueError("User models cannot be written into the official model directory")
    model_id = "user-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    target = root / model_id
    target.mkdir(parents=True, exist_ok=False)
    artifact = target / "model.joblib"
    joblib.dump(pipe, artifact)
    metadata = {"model_id": model_id, "model_family": model_family, "target_column": target_column, "target_unit": unit, "feature_order": FEATURES, "validation_protocol": "GroupShuffleSplit holdout and GroupKFold CV by canonical isomeric SMILES", "metrics": metrics, "model_sha256": sha256(artifact)}
    (target / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    return target, metadata
