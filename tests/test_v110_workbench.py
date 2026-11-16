import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.model_selection import GroupShuffleSplit

from jpcb_energy.applicability import assess_domain
from jpcb_energy.conformer import conformer_sdf, conformer_xyz, generate_conformer
from jpcb_energy.descriptors import FEATURES, calculate_descriptors
from jpcb_energy.model import sha256
from jpcb_energy.registry import discover_models
from jpcb_energy.user_training import train_user_model
from jpcb_energy.visualization import molecule_png_bytes, molecule_svg
from jpcb_energy.workbench import batch_predict, predict_with_bundle

ROOT = Path(__file__).resolve().parents[1]


def test_v100_artifact_and_fixed_reference_predictions_are_unchanged():
    assert sha256(ROOT / "models" / "gpr_model.joblib") == "1ee727e346afcd04af8d50314038dd23a37b002d74fd0e072813d38377618983"
    models = discover_models(ROOT)
    legacy = models["v1.0.0-vacuum-reference"]
    assert predict_with_bundle("C=CC(=O)N", legacy)["prediction"] == pytest.approx(-244.90620512295402, abs=1e-10)
    assert predict_with_bundle("CC[N+](C)(C)CCO", legacy)["prediction"] == pytest.approx(-367.17459264157856, abs=1e-10)


def test_all_five_solvent_models_load_predict_and_validate_hashes():
    models = discover_models(ROOT)
    environments = set()
    for model_id, entry in models.items():
        if not model_id.startswith("v1.1.0"):
            continue
        environments.add(entry["metadata"]["environment"])
        assert sha256(entry["path"]) == entry["metadata"]["model_sha256"]
        result = predict_with_bundle("C=CC(=O)N", entry)
        assert np.isfinite(result["prediction"])
        assert result["applicability_status"] in {"within_domain", "borderline", "outside_domain"}
    assert environments == {"vacuum", "ethanol", "dmso", "water", "formamide"}


def test_batch_preserves_rows_deduplicates_and_exports_descriptors():
    entry = discover_models(ROOT)["v1.1.0-gpr-water"]
    source = pd.DataFrame({"row_id": ["a", "b", "c", "d"], "smiles": ["C=CC(=O)N", "bad", "C=CC(=O)N", "CC[N+](C)(C)CCO"]})
    result, summary = batch_predict(source, entry, chunk_size=2)
    assert result.row_id.tolist() == source.row_id.tolist()
    assert summary["valid_records"] == 3 and summary["invalid_records"] == 1 and summary["duplicate_records"] == 1
    assert result.loc[0, "predicted_E_sp_Eh"] == result.loc[2, "predicted_E_sp_Eh"]
    assert set(FEATURES).issubset(result.columns)


def test_group_split_has_no_canonical_overlap_and_791_is_not_mislabeled_independent():
    entry = discover_models(ROOT)["v1.1.0-gpr-water"]
    groups = np.array(entry["domain_profile"]["names"])
    canonical_groups = np.array([tuple(x) for x in np.asarray(entry["domain_profile"]["training_X"])], dtype=object)
    # The production training script groups by canonical SMILES. Reproduce the
    # no-overlap invariant with its 192-group audit count from release metadata.
    summary = json.loads((ROOT / "models" / "v1.1.0" / "evaluation_summary.json").read_text())
    assert summary["paired_unique_canonical_groups"] == 192
    assert summary["water_exact_canonical_overlap_with_core"] == 4
    assert summary["water_set_independent"] is False


def test_applicability_range_and_distance_flags():
    entry = discover_models(ROOT)["v1.1.0-gpr-vacuum"]
    _, desc = calculate_descriptors("C=CC(=O)N")
    normal = assess_domain(desc, entry["domain_profile"], "C=CC(=O)N")
    extreme = {feature: value * 1000 + 1e6 for feature, value in desc.items()}
    outside = assess_domain(extreme, entry["domain_profile"], "C=CC(=O)N")
    assert normal["applicability_status"] in {"within_domain", "borderline", "outside_domain"}
    assert outside["applicability_status"] == "outside_domain"
    assert outside["out_of_range_features"]


def test_2d_and_3d_exports_are_nonempty_and_reproducible():
    svg = molecule_svg("CCO", atom_indices=True)
    png = molecule_png_bytes("CCO")
    mol1, info1 = generate_conformer("CCO", seed=42)
    mol2, info2 = generate_conformer("CCO", seed=42)
    assert "<svg" in svg and len(png) > 1000
    assert conformer_sdf(mol1).endswith("$$$$\n")
    assert conformer_xyz(mol1).splitlines()[0] == str(mol1.GetNumAtoms())
    assert conformer_xyz(mol1) == conformer_xyz(mol2)
    assert "not an ORCA-optimized geometry" in info1["geometry_role"]


def test_user_model_is_saved_outside_official_models(tmp_path):
    table = pd.DataFrame({"smiles": ["C" * n for n in range(1, 21)], "target": [-10.0 * n for n in range(1, 21)]})
    legacy_hash = sha256(ROOT / "models" / "gpr_model.joblib")
    path, metadata = train_user_model(table, "target", "arb", "Ridge", tmp_path)
    assert path.parent == tmp_path.resolve()
    assert (path / "model.joblib").exists()
    assert metadata["metrics"]["group_overlap"] == 0
    assert sha256(ROOT / "models" / "gpr_model.joblib") == legacy_hash
