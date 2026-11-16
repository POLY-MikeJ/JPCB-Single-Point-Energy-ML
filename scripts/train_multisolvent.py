#!/usr/bin/env python
"""Build paired five-environment datasets, models, and external water evaluation."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from rdkit import Chem, DataStructs
from rdkit.Chem import rdFingerprintGenerator
from sklearn.base import clone
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold, GroupShuffleSplit, KFold, cross_val_predict, train_test_split

from jpcb_energy.applicability import build_domain_profile
from jpcb_energy.descriptors import FEATURES, calculate_descriptors, calculate_rdkit_panel, standardize_smiles
from jpcb_energy.model import build_pipeline, sha256
from jpcb_energy.orca_parser import parse_orca

ENVIRONMENTS = ["vacuum", "ethanol", "dmso", "water", "formamide"]


def metrics(y, pred) -> dict:
    residual = np.asarray(pred) - np.asarray(y)
    absolute = np.abs(residual)
    return {
        "mae_Eh": float(mean_absolute_error(y, pred)),
        "rmse_Eh": float(mean_squared_error(y, pred) ** 0.5),
        "r2": float(r2_score(y, pred)),
        "median_absolute_error_Eh": float(np.median(absolute)),
        "residual_mean_Eh": float(np.mean(residual)),
        "residual_std_Eh": float(np.std(residual)),
        "absolute_error_p90_Eh": float(np.quantile(absolute, 0.90)),
        "absolute_error_p95_Eh": float(np.quantile(absolute, 0.95)),
        "maximum_absolute_error_Eh": float(np.max(absolute)),
    }


def plot_diagnostics(frame: pd.DataFrame, out: Path, title: str) -> None:
    out.mkdir(parents=True, exist_ok=True)
    specs = [
        ("parity", frame.y_true_Eh, frame.y_pred_Eh, "DFT E_sp (Eh)", "Predicted E_sp (Eh)"),
        ("residual", frame.y_pred_Eh, frame.residual_Eh, "Predicted E_sp (Eh)", "Residual (Eh)"),
        ("residual_vs_heavy_atoms", frame.heavy_atom_count, frame.residual_Eh, "Heavy atom count", "Residual (Eh)"),
        ("residual_vs_total_atoms", frame.total_atom_count, frame.residual_Eh, "Total atom count", "Residual (Eh)"),
        ("residual_vs_formal_charge", frame.formal_charge, frame.residual_Eh, "Formal charge", "Residual (Eh)"),
    ]
    for name, x, y, xlabel, ylabel in specs:
        fig, ax = plt.subplots(figsize=(6.4, 5.2), dpi=160)
        ax.scatter(x, y, s=22, alpha=0.78, color="#2471A3")
        if name == "parity":
            lo, hi = min(x.min(), y.min()), max(x.max(), y.max())
            ax.plot([lo, hi], [lo, hi], "k--", lw=1)
        else:
            ax.axhline(0, color="black", ls="--", lw=1)
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
        fig.tight_layout(); fig.savefig(out / f"{name}.png"); plt.close(fig)


def read_core(calc_root: Path, features: pd.DataFrame, monomers: pd.DataFrame) -> dict[str, pd.DataFrame]:
    mapping = monomers.set_index("name")
    feature_map = features.set_index("name")
    datasets = {}
    expected_names = None
    for environment in ENVIRONMENTS:
        out_dir = calc_root / "ORCA-209 Molecules" / "209freq" / f"freq_outs_{environment}"
        input_dir = calc_root / "ORCA-209 Molecules" / "209freq" / f"freq_inps_{environment}"
        out_files = {p.stem: p for p in out_dir.glob("*.out")}
        input_files = {p.stem: p for p in input_dir.glob("*.inp")}
        if len(out_files) != 209 or set(out_files) != set(mapping.index) & set(out_files):
            missing = set(out_files) - set(mapping.index)
            raise ValueError(f"{environment}: expected 209 exactly mapped outputs; unmapped={sorted(missing)}")
        if expected_names is None:
            expected_names = set(out_files)
        elif set(out_files) != expected_names:
            raise ValueError(f"{environment}: molecule membership differs from the paired core set")
        rows = []
        for name in sorted(out_files):
            parsed = parse_orca(out_files[name])
            if not parsed["normal_termination"] or parsed["task_type"] != "frequency":
                raise ValueError(f"Invalid frequency output: {out_files[name]}")
            if name not in input_files:
                raise ValueError(f"Missing exact-stem input for {name} in {environment}")
            source = mapping.loc[name]
            canonical, _ = standardize_smiles(source.smiles)
            _, panel = calculate_rdkit_panel(source.smiles)
            row = {
                "record_id": f"ORCA209-{environment.upper()}-FREQ-{name}", "name": name, "smiles": source.smiles,
                "canonical_smiles": canonical, "environment": environment, "dielectric_constant": parsed["dielectric_constant"],
                "method": parsed["method"], "basis_set": parsed["basis_set"], "charge": parsed["charge"], "multiplicity": parsed["multiplicity"],
                "target_Eh": parsed["final_single_point_energy_Eh"], "normal_termination": parsed["normal_termination"],
                "source_output_sha256": parsed["sha256"], "source_output": str(out_files[name]), "source_input": str(input_files[name]),
                "heavy_atom_count": int(panel["HeavyAtomCount"]), "total_atom_count": int(panel["TotalAtomCount_with_H"]), "formal_charge": int(panel["FormalCharge"]),
            }
            row.update({feature: float(feature_map.loc[name, feature]) for feature in FEATURES})
            rows.append(row)
        datasets[environment] = pd.DataFrame(rows)
    return datasets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--calc-root", type=Path, required=True)
    parser.add_argument("--feature-table", type=Path, required=True)
    parser.add_argument("--monomers", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--model-root", type=Path, default=Path("models/v1.1.0"))
    parser.add_argument("--results", type=Path, default=Path("validation_results/v1.1.0"))
    args = parser.parse_args()
    args.model_root.mkdir(parents=True, exist_ok=True); args.results.mkdir(parents=True, exist_ok=True)
    feature_table = pd.read_csv(args.feature_table)
    monomers, library = pd.read_csv(args.monomers), pd.read_csv(args.library)
    datasets = read_core(args.calc_root, feature_table, monomers)

    protocol_audit = []
    excluded_names: set[str] = set()
    for environment, frame in datasets.items():
        expected_epsilon = float(frame.dielectric_constant.mode().iloc[0])
        for _, row in frame.iterrows():
            consistent = bool(np.isclose(float(row.dielectric_constant), expected_epsilon))
            protocol_audit.append({"environment": environment, "name": row["name"], "observed_dielectric_constant": row.dielectric_constant, "expected_environment_dielectric_constant": expected_epsilon, "protocol_consistent": consistent, "source_input": row.source_input, "source_output": row.source_output})
            if not consistent:
                excluded_names.add(row["name"])
    pd.DataFrame(protocol_audit).to_csv(args.results / "protocol_consistency_audit.csv", index=False)
    if excluded_names:
        datasets = {environment: frame[~frame.name.isin(excluded_names)].reset_index(drop=True) for environment, frame in datasets.items()}

    identity = datasets["vacuum"][["record_id", "name", "smiles", "canonical_smiles", "charge", "formal_charge", "multiplicity"]].copy()
    identity["canonical_duplicate_count"] = identity.groupby("canonical_smiles").canonical_smiles.transform("size")
    identity.to_csv(args.results / "duplicate_identity_audit.csv", index=False)
    common = datasets["vacuum"]
    groups = common.canonical_smiles
    group_split = GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42)
    group_train, group_test = next(group_split.split(common[FEATURES], common.target_Eh, groups))
    if set(groups.iloc[group_train]) & set(groups.iloc[group_test]):
        raise AssertionError("Canonical group leakage in holdout")
    unique_groups = groups.nunique()
    fold_count = min(5, unique_groups)
    comparison = []

    for environment, frame in datasets.items():
        environment_dir = args.results / environment
        environment_dir.mkdir(parents=True, exist_ok=True)
        frame.to_csv(environment_dir / "dataset_manifest.csv", index=False)
        X, y = frame[FEATURES], frame.target_Eh
        random_train, random_test = train_test_split(np.arange(len(frame)), test_size=0.2, random_state=42)
        random_model = build_pipeline(42).fit(X.iloc[random_train], y.iloc[random_train])
        random_pred = random_model.predict(X.iloc[random_test])
        group_model = build_pipeline(42).fit(X.iloc[group_train], y.iloc[group_train])
        group_pred = group_model.predict(X.iloc[group_test])
        group_cv = GroupKFold(fold_count)
        cv_pred = cross_val_predict(build_pipeline(42), X, y, groups=groups, cv=group_cv)
        result_metrics = {
            "environment": environment, "n_records": len(frame), "n_unique_structure_groups": int(unique_groups),
            "group_holdout_train_records": len(group_train), "group_holdout_test_records": len(group_test),
            "group_holdout_train_groups": int(groups.iloc[group_train].nunique()), "group_holdout_test_groups": int(groups.iloc[group_test].nunique()), "train_test_group_overlap": 0,
            "legacy_random_holdout": metrics(y.iloc[random_test], random_pred),
            "group_holdout": metrics(y.iloc[group_test], group_pred),
            "group_kfold_cv": metrics(y, cv_pred),
        }
        (environment_dir / "metrics.json").write_text(json.dumps(result_metrics, indent=2), encoding="utf-8")
        predictions = frame.iloc[group_test][["record_id", "name", "canonical_smiles", "heavy_atom_count", "total_atom_count", "formal_charge"]].copy()
        predictions["y_true_Eh"] = y.iloc[group_test].to_numpy(); predictions["y_pred_Eh"] = group_pred; predictions["residual_Eh"] = group_pred - y.iloc[group_test].to_numpy()
        predictions.to_csv(environment_dir / "group_holdout_predictions.csv", index=False)
        plot_diagnostics(predictions, environment_dir / "figures", f"{environment.title()} group-aware holdout")

        final = build_pipeline(42).fit(X, y)
        profile = build_domain_profile(X, frame.record_id, frame.name)
        bundle = {"pipeline": final, "domain_profile": profile}
        model_dir = args.model_root / f"gpr_{environment}"; model_dir.mkdir(parents=True, exist_ok=True)
        artifact = model_dir / "model.joblib"; joblib.dump(bundle, artifact)
        eps_values = sorted(frame.dielectric_constant.dropna().unique().tolist())
        metadata = {
            "model_id": f"v1.1.0-gpr-{environment}", "model_version": "1.1.0", "environment": environment,
            "dielectric_constant": eps_values[0] if len(eps_values) == 1 else eps_values,
            "dielectric_source": "Parsed from ORCA output CPCM Epsilon; vacuum recorded as 1.0",
            "target_definition": "ORCA FINAL SINGLE POINT ENERGY from the environment-specific frequency job at its optimized geometry; electronic SCF energy without ZPE or thermal correction",
            "target_unit": "Eh", "feature_order": FEATURES, "training_records": len(frame), "unique_structure_groups": int(unique_groups),
            "method": sorted(frame.method.dropna().unique().tolist()), "basis_set": sorted(frame.basis_set.dropna().unique().tolist()),
            "validation": result_metrics, "protocol_excluded_records": sorted(excluded_names), "domain_thresholds": {k: profile[k] for k in ["distance_borderline", "distance_outside", "threshold_protocol"]},
            "software_versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__}, "model_sha256": sha256(artifact),
        }
        (model_dir / "model_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        comparison.append({"environment": environment, "dielectric_constant": metadata["dielectric_constant"], **{f"group_holdout_{k}": v for k, v in result_metrics["group_holdout"].items()}, **{f"group_cv_{k}": v for k, v in result_metrics["group_kfold_cv"].items()}})
    pd.DataFrame(comparison).to_csv(args.results / "solvent_comparison_metrics.csv", index=False)

    # Water-only 791-record additional evaluation set.
    outputs = {p.stem: p for p in (args.calc_root / "ORCA-791 Molecules" / "791freq" / "freq_outs_water").glob("*.out")}
    inputs = {p.stem: p for p in (args.calc_root / "ORCA-791 Molecules" / "791freq" / "freq_inps_water").glob("*.inp")}
    lib = library.set_index("name")
    if len(outputs) != 791 or set(outputs) - set(lib.index) or set(outputs) - set(inputs):
        raise ValueError("The 791-record water set is not exactly one-to-one mapped to library/input/output stems")
    ext_rows = []
    for index, name in enumerate(sorted(outputs), 1):
        parsed = parse_orca(outputs[name])
        if not parsed["normal_termination"]:
            raise ValueError(f"Abnormal external output: {outputs[name]}")
        source = lib.loc[name]; canonical, desc = calculate_descriptors(source.smiles); _, panel = calculate_rdkit_panel(source.smiles)
        ext_rows.append({"record_id": f"ORCA791-WATER-FREQ-{name}", "name": name, "smiles": source.smiles, "canonical_smiles": canonical, "formal_charge_table": source.formal_charge, "charge_type": source.charge_type, "charge_orca": parsed["charge"], "multiplicity": parsed["multiplicity"], "dielectric_constant": parsed["dielectric_constant"], "target_Eh": parsed["final_single_point_energy_Eh"], "heavy_atom_count": int(panel["HeavyAtomCount"]), "total_atom_count": int(panel["TotalAtomCount_with_H"]), **desc})
    ext = pd.DataFrame(ext_rows)
    core_water = datasets["water"]
    overlap = set(ext.canonical_smiles) & set(core_water.canonical_smiles)
    ext["exact_core_structure_overlap"] = ext.canonical_smiles.isin(overlap)
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    core_fp = [generator.GetFingerprint(Chem.MolFromSmiles(s)) for s in core_water.canonical_smiles]
    ext["maximum_core_tanimoto"] = [max(DataStructs.BulkTanimotoSimilarity(generator.GetFingerprint(Chem.MolFromSmiles(s)), core_fp)) for s in ext.canonical_smiles]
    water_bundle = joblib.load(args.model_root / "gpr_water" / "model.joblib")
    mean, std = water_bundle["pipeline"].predict(ext[FEATURES], return_std=True)
    ext["predicted_Eh"] = mean; ext["predictive_std_Eh"] = std; ext["residual_Eh"] = mean - ext.target_Eh; ext["absolute_error_Eh"] = ext.residual_Eh.abs()
    ext.to_csv(args.results / "water_791_predictions.csv", index=False)
    ext_metrics = metrics(ext.target_Eh, mean)
    ext_metrics.update({"n_records": len(ext), "exact_canonical_overlap_with_core": len(overlap), "duplicate_canonical_structures_within_791": int(ext.duplicated("canonical_smiles", keep=False).sum()), "near_duplicate_count_tanimoto_ge_0_95": int((ext.maximum_core_tanimoto >= 0.95).sum()), "set_designation": "additional external evaluation set; not claimed independent because selection provenance independence is not established"})
    ext_metrics["residual_quantiles_Eh"] = {str(q): float(ext.residual_Eh.quantile(q)) for q in [0.05, 0.25, 0.5, 0.75, 0.95]}
    (args.results / "water_791_metrics.json").write_text(json.dumps(ext_metrics, indent=2), encoding="utf-8")
    plot_frame = ext.rename(columns={"target_Eh": "y_true_Eh", "predicted_Eh": "y_pred_Eh", "charge_orca": "formal_charge"})
    plot_diagnostics(plot_frame, args.results / "water_791_figures", "Water 791-record additional evaluation")
    print(json.dumps({"core_counts": {k: len(v) for k, v in datasets.items()}, "protocol_excluded_records": sorted(excluded_names), "unique_groups": int(unique_groups), "water_791": ext_metrics}, indent=2))


if __name__ == "__main__":
    main()
