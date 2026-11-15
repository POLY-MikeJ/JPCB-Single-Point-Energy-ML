#!/usr/bin/env python
"""Train and validate the verified 209-record published GPR workflow."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from datetime import date
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, r2_score
from sklearn.model_selection import KFold, cross_val_predict, train_test_split

from jpcb_energy.descriptors import FEATURES
from jpcb_energy.model import build_pipeline, sha256
from jpcb_energy.orca_parser import parse_orca


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature-table", type=Path, required=True)
    parser.add_argument("--orca-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("models"))
    parser.add_argument("--results", type=Path, default=Path("validation_results"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    args.results.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(args.feature_table)
    orca_names = {p.stem for p in args.orca_dir.glob("*.out")}
    verified = df[df["name"].isin(orca_names)].copy()
    if len(verified) != 209 or set(verified["name"]) != orca_names:
        raise ValueError(f"Expected exactly 209 one-to-one ORCA records; found {len(verified)}")
    if verified[FEATURES].isna().any().any():
        raise ValueError("Selected feature table contains missing values")

    orca_energy = {}
    for path in args.orca_dir.glob("*.out"):
        parsed = parse_orca(path)
        if not parsed["normal_termination"] or parsed["task_type"] != "frequency":
            raise ValueError(f"Not a normally terminated frequency output: {path}")
        orca_energy[path.stem] = parsed["final_single_point_energy_Eh"]
    verified["orca_target_Eh"] = verified["name"].map(orca_energy)
    verified["source_table_delta_Eh"] = verified["target"] - verified["orca_target_Eh"]
    max_delta = float(verified["source_table_delta_Eh"].abs().max())
    verified[["name", "smiles", "target", "orca_target_Eh", "source_table_delta_Eh"]].to_csv(
        args.results / "orca_label_validation.csv", index=False
    )

    X, y = verified[FEATURES], verified["orca_target_Eh"]
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = build_pipeline(42)
    model.fit(X_train, y_train)
    train_pred = model.predict(X_train)
    test_pred = model.predict(X_test)
    cv = KFold(n_splits=5, shuffle=True, random_state=42)
    cv_pred = cross_val_predict(clone(model), X, y, cv=cv)
    metrics = {
        "n_verified_records": int(len(verified)),
        "n_train": int(len(X_train)),
        "n_test": int(len(X_test)),
        "random_state": 42,
        "test_size": 0.2,
        "cv_folds": 5,
        "maximum_source_table_vs_orca_delta_Eh": max_delta,
        "train_mae_Eh": float(mean_absolute_error(y_train, train_pred)),
        "train_r2": float(r2_score(y_train, train_pred)),
        "test_mae_Eh": float(mean_absolute_error(y_test, test_pred)),
        "test_r2": float(r2_score(y_test, test_pred)),
        "cv_mae_Eh": float(mean_absolute_error(y, cv_pred)),
        "cv_r2": float(r2_score(y, cv_pred)),
    }

    final_model = build_pipeline(42)
    final_model.fit(X, y)
    model_path = args.output / "gpr_model.joblib"
    joblib.dump(final_model, model_path)
    metadata = {
        "model_version": "1.0.0",
        "created": str(date.today()),
        "article_doi": "10.1021/acs.jpcb.6c02936",
        "model_type": "complete sklearn Pipeline: median imputer, standard scaler, GPR",
        "feature_order": FEATURES,
        "target_definition": "ORCA FINAL SINGLE POINT ENERGY from the vacuum frequency calculation at the optimized geometry; electronic SCF energy without thermal correction",
        "target_unit": "Eh",
        "training_data_version": "verified-orca-209-v1",
        "training_record_count": 209,
        "source_feature_table_sha256": file_hash(args.feature_table),
        "model_sha256": "",
        "software_versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__},
        "validation_metrics": metrics,
        "applicability_domain": "Curated closed-shell, polar or charged polymerizable monomers represented by the training descriptor space; exclude metals, radicals, zwitterions, explicit ion pairs, and oligomers without independent validation.",
    }
    metadata["model_sha256"] = sha256(model_path)
    (args.output / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    (args.results / "metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    rows = []
    for indices, truth, pred, split in [
        (y_train.index, y_train, train_pred, "train"),
        (y_test.index, y_test, test_pred, "test"),
    ]:
        for idx, yt, yp in zip(indices, truth, pred):
            rows.append({"record_id": f"ORCA209-VAC-FREQ-{verified.loc[idx, 'name']}", "name": verified.loc[idx, "name"], "split": split, "y_true_Eh": yt, "y_pred_Eh": yp, "residual_Eh": yp - yt})
    predictions = pd.DataFrame(rows)
    predictions.to_csv(args.results / "predictions.csv", index=False)

    for filename, x, yplot, xlabel, ylabel in [
        ("parity_plot.png", predictions["y_true_Eh"], predictions["y_pred_Eh"], "DFT E_sp (Eh)", "Predicted E_sp (Eh)"),
        ("residual_plot.png", predictions["y_pred_Eh"], predictions["residual_Eh"], "Predicted E_sp (Eh)", "Residual (Eh)"),
    ]:
        fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=160)
        ax.scatter(x, yplot, c=predictions["split"].map({"train": "#2471A3", "test": "#C0392B"}), s=24, alpha=0.8)
        if filename.startswith("parity"):
            lo, hi = min(x.min(), yplot.min()), max(x.max(), yplot.max())
            ax.plot([lo, hi], [lo, hi], "k--", lw=1)
        else:
            ax.axhline(0, color="black", ls="--", lw=1)
        ax.set(xlabel=xlabel, ylabel=ylabel)
        fig.tight_layout()
        fig.savefig(args.results / filename)
        plt.close(fig)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()

