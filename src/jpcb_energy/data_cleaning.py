"""Reversible outlier screening for audited ORCA-derived datasets.

All functions operate on dataframe copies. They never edit raw ORCA files or the
published model artifacts.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupKFold


@dataclass(frozen=True)
class CleaningConfig:
    iqr_multiplier: float = 1.5
    z_threshold: float = 3.0
    mad_threshold: float = 3.5
    isolation_contamination: float = 0.02
    composition_threshold: float = 3.5


INVALID_FLAGS = {
    "scf_not_converged", "formal_charge_mismatch", "atom_count_mismatch",
    "element_composition_mismatch", "solvent_protocol_mismatch",
    "substantive_imaginary_frequency", "duplicate_result_mismatch",
    "calculation_protocol_error", "abnormal_termination",
}


def _group_score(values: pd.Series, method: str) -> pd.Series:
    values = pd.to_numeric(values, errors="coerce")
    if method == "z":
        scale = values.std(ddof=0)
        return (values - values.mean()).abs() / scale if scale and np.isfinite(scale) else pd.Series(0.0, index=values.index)
    median = values.median(); mad = (values - median).abs().median()
    return 0.67448975 * (values - median).abs() / mad if mad and np.isfinite(mad) else pd.Series(0.0, index=values.index)


def detect_outliers(frame: pd.DataFrame, config: CleaningConfig = CleaningConfig()) -> pd.DataFrame:
    """Return the audit table plus transparent, independently inspectable flags."""
    output = frame.copy().reset_index(drop=True)
    energy = pd.to_numeric(output["final_single_point_energy_Eh"], errors="coerce")
    groups = output.get("environment", pd.Series("all", index=output.index)).fillna("unknown")
    output["iqr_outlier"] = False; output["zscore_outlier"] = False; output["mad_outlier"] = False
    for _, idx in groups.groupby(groups).groups.items():
        values = energy.loc[idx]; q1, q3 = values.quantile([0.25, 0.75]); spread = q3 - q1
        output.loc[idx, "iqr_outlier"] = ((values < q1 - config.iqr_multiplier * spread) | (values > q3 + config.iqr_multiplier * spread)).fillna(False)
        output.loc[idx, "zscore_outlier"] = (_group_score(values, "z") > config.z_threshold).fillna(False)
        output.loc[idx, "mad_outlier"] = (_group_score(values, "mad") > config.mad_threshold).fillna(False)

    residual = pd.to_numeric(output.get("composition_oof_residual_Eh"), errors="coerce")
    robust = pd.to_numeric(output.get("composition_robust_z"), errors="coerce")
    output["composition_residual_outlier"] = robust.abs().gt(config.composition_threshold).fillna(False)
    features = pd.DataFrame({"energy": energy, "residual": residual, "atoms": pd.to_numeric(output.get("atom_count"), errors="coerce")})
    features = features.fillna(features.median()).fillna(0.0)
    if len(features) >= 10:
        prediction = IsolationForest(contamination=config.isolation_contamination, random_state=42, n_estimators=200).fit_predict(features)
        output["isolation_forest_outlier"] = prediction == -1
    else:
        output["isolation_forest_outlier"] = False

    flag_sets = output.get("qc_flags", pd.Series("", index=output.index)).fillna("").map(lambda value: set(str(value).split(";")) - {""})
    abnormal = ~output.get("normal_termination", pd.Series(True, index=output.index)).fillna(False).astype(bool)
    scf_failed = output.get("qc_status", pd.Series("", index=output.index)).fillna("").isin(["invalid_calculation", "unmatched"])
    output["orca_qc_invalid"] = abnormal | scf_failed | flag_sets.map(lambda flags: bool(flags & INVALID_FLAGS))
    # A canonical-SMILES collision may represent separately named stereochemical,
    # conformational or protonation records. Only repeated record IDs under the
    # same protocol are treated as duplicates eligible for category A.
    duplicate_range = output.groupby(["record_id", "environment"], dropna=False)["final_single_point_energy_Eh"].transform(lambda values: pd.to_numeric(values, errors="coerce").max() - pd.to_numeric(values, errors="coerce").min())
    output["duplicate_inconsistent"] = duplicate_range.gt(1e-4).fillna(False)
    output["clearly_invalid"] = output["orca_qc_invalid"] | output["duplicate_inconsistent"]
    statistical = ["iqr_outlier", "zscore_outlier", "mad_outlier", "isolation_forest_outlier", "composition_residual_outlier"]
    output["statistical_suspect"] = output[statistical].any(axis=1) & ~output["clearly_invalid"]
    reason_columns = statistical + ["orca_qc_invalid", "duplicate_inconsistent"]
    output["outlier_reasons"] = output.apply(lambda row: ";".join(name for name in reason_columns if bool(row[name])), axis=1)
    output["outlier_category"] = np.select([output.clearly_invalid, output.statistical_suspect], ["A: clearly invalid", "B: statistical suspect"], default="retained")
    return output


def apply_removal(detected: pd.DataFrame, record_keys: set[str] | list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    keys = {str(key) for key in record_keys}; mask = detected.record_key.astype(str).isin(keys)
    excluded = detected.loc[mask].copy(); cleaned = detected.loc[~mask].copy()
    excluded["cleaning_action"] = "excluded_from_working_copy"
    return cleaned.reset_index(drop=True), excluded.reset_index(drop=True)


def cleaning_report(original: pd.DataFrame, cleaned: pd.DataFrame, excluded: pd.DataFrame, config: CleaningConfig, action: str) -> dict:
    return {
        "schema_version": "1.0", "created_utc": datetime.now(timezone.utc).isoformat(),
        "action": action, "non_destructive": True,
        "raw_orca_files_modified": False, "published_models_modified": False,
        "original_records": int(len(original)), "cleaned_records": int(len(cleaned)), "excluded_records": int(len(excluded)),
        "excluded_by_category": excluded.get("outlier_category", pd.Series(dtype=str)).value_counts().to_dict(),
        "configuration": asdict(config),
        "scientific_boundary": "Statistical flags are review signals. Cleaned-model diagnostics are not published JPCB results.",
    }


def persist_cleaning_bundle(original: pd.DataFrame, removed_keys: set[str], directory: Path, config: CleaningConfig, action: str = "user_selected") -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True); detected = detect_outliers(original, config); cleaned, excluded = apply_removal(detected, removed_keys)
    report = cleaning_report(detected, cleaned, excluded, config, action)
    cleaned_path = directory / "dataset_cleaned_v1.csv"; excluded_path = directory / "excluded_records.csv"; report_path = directory / "cleaning_report.json"
    cleaned.to_csv(cleaned_path, index=False); excluded.to_csv(excluded_path, index=False); report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"cleaned": cleaned_path, "excluded": excluded_path, "report": report_path}


def compare_composition_models(detected: pd.DataFrame, removed_keys: set[str]) -> pd.DataFrame:
    """Compare reproducible composition baselines, never the published GPR claim."""
    rows = []
    for label, data in [("original audit", detected), ("cleaned working copy", detected[~detected.record_key.astype(str).isin(removed_keys)])]:
        data = data.dropna(subset=["final_single_point_energy_Eh", "canonical_smiles"]).copy()
        elements = sorted({element for value in data.element_counts.fillna("{}") for element in json.loads(value or "{}").keys()})
        x = np.array([[json.loads(value or "{}").get(e, 0) for e in elements] + [float(charge or 0)] for value, charge in zip(data.element_counts, data.charge)], float)
        y = data.final_single_point_energy_Eh.to_numpy(float); groups = data.canonical_smiles.to_numpy(); predictions = np.full(len(data), np.nan)
        splits = min(5, len(set(groups)))
        if splits < 2: continue
        for train, test in GroupKFold(splits).split(x, y, groups): predictions[test] = Ridge(alpha=1.0).fit(x[train], y[train]).predict(x[test])
        rows.append({"dataset": label, "records": len(data), "group_folds": splits, "MAE_Eh": mean_absolute_error(y, predictions), "RMSE_Eh": mean_squared_error(y, predictions) ** 0.5, "R2": r2_score(y, predictions), "claim_scope": "diagnostic composition baseline; not published JPCB model"})
    return pd.DataFrame(rows)
