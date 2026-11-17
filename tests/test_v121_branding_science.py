import json
from pathlib import Path

import pandas as pd
import pytest
from rdkit import Chem
from streamlit.testing.v1 import AppTest

from jpcb_energy.data_qc import parse_geometry, reversible_inclusion
from jpcb_energy.provenance import ARTICLE_DOI, PRODUCT_NAME, SOFTWARE_VERSION, add_prediction_metadata, prediction_workbook
from jpcb_energy.registry import discover_models
from jpcb_energy.workbench import predict_with_bundle
from jpcb_energy.xtb import molecule_from_xyz


ROOT = Path(__file__).resolve().parents[1]


def test_branding_citation_and_metadata_are_consistent():
    assert PRODUCT_NAME == "ZHU MolEnergy Workbench" and SOFTWARE_VERSION == "1.4.0"
    assert ARTICLE_DOI == "10.1021/acs.jpcb.6c02936"
    assert 'title: "ZHU MolEnergy Workbench' in (ROOT / "CITATION.cff").read_text(encoding="utf-8")
    assert "10.1021/acs.jpcb.6c02936" in (ROOT / "CITATION.bib").read_text(encoding="utf-8")


def test_prediction_exports_carry_model_and_article_provenance():
    frame = pd.DataFrame({"smiles": ["C=CC(=O)N"], "predicted_E_sp_Eh": [-244.0]})
    metadata = {"model_version": "1.0.0", "environment": "vacuum", "target_definition": "electronic energy", "target_unit": "Eh"}
    enriched = add_prediction_metadata(frame, "v1.0.0-vacuum-reference", metadata)
    assert enriched.loc[0, "article_doi"] == ARTICLE_DOI
    assert enriched.loc[0, "model_version"] == "1.0.0"
    assert len(prediction_workbook(frame, "v1.0.0-vacuum-reference", metadata)) > 4000


def test_reference_model_actual_prediction_is_stable():
    entry = discover_models(ROOT)["v1.0.0-vacuum-reference"]
    result = predict_with_bundle("C=CC(=O)N", entry)
    assert result["canonical_smiles"] == "C=CC(N)=O"
    # BLAS/scikit-learn builds differ at about 1e-9 Eh on Windows runners.
    assert result["prediction"] == pytest.approx(-244.90620512295402, abs=1e-8)


def test_app_invalidates_stale_prediction_after_smiles_change():
    app = AppTest.from_file(str(ROOT / "src" / "jpcb_energy" / "app.py"), default_timeout=30).run()
    app.button(key="predict_button").click().run(timeout=30)
    assert any("Eh" in metric.value for metric in app.metric)
    nearest = [item.value for item in app.markdown if "Nearest training record" in item.value]
    assert nearest == ["Nearest training record: **not available** · distance **not available**"]
    assert "nan" not in nearest[0].lower()
    app.text_input(key="predict_smiles").set_value("CCO").run(timeout=30)
    assert not any("Electronic energy" == metric.label for metric in app.metric)
    assert any("Run prediction again" in info.value for info in app.info)


def test_charge_identity_and_missing_geometry_are_precise(tmp_path):
    inp = tmp_path / "charged.inp"
    inp.write_text("* xyz 1 1\nC 0 0 0\nH 0 0 1.1\n*\n", encoding="utf-8")
    geometry = parse_geometry(inp)
    assert geometry["geometry_charge"] == 1 and geometry["atom_count"] == 2
    with pytest.raises((FileNotFoundError, ValueError)):
        molecule_from_xyz(Chem.AddHs(Chem.MolFromSmiles("C")), tmp_path / "missing.xyz")


def test_review_decision_vocabulary_is_reversible():
    frame = pd.DataFrame({"record_key": ["x"], "qc_status": ["needs_review"]})
    quarantined = reversible_inclusion(frame, pd.DataFrame({"record_key": ["x"], "review_decision": ["quarantine"], "reviewed_by": ["A"], "reviewed_at": ["2026-11-16"]}))
    included = reversible_inclusion(frame, pd.DataFrame({"record_key": ["x"], "review_decision": ["include"], "reviewed_by": ["A"], "reviewed_at": ["2026-11-16"]}))
    assert not bool(quarantined.loc[0, "include_verified_strict"])
    assert bool(included.loc[0, "include_verified_strict"])


def test_launcher_and_shortcut_use_new_product_name():
    assert (ROOT / "Launch_ZHU_MolEnergy.bat").is_file()
    installer = (ROOT / "Install_ZHU_MolEnergy_Desktop_Shortcut.ps1").read_text(encoding="utf-8")
    assert "ZHU MolEnergy Workbench.lnk" in installer
    assert "ExpectedTargets -contains" in installer
    source = (ROOT / "scripts" / "launcher.py").read_text(encoding="utf-8")
    assert "Starting ZHU MolEnergy Workbench" in source
