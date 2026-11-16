import json

import pandas as pd
from rdkit import Chem

from jpcb_energy.conformer import conformer_mol, generate_conformer, plotly_figure
from jpcb_energy.data_cleaning import CleaningConfig, apply_removal, detect_outliers, persist_cleaning_bundle
from jpcb_energy.provenance import ACS_CITATION, BIBTEX_CITATION, prediction_metadata


def _audit():
    rows=[]
    for index, energy in enumerate([-10.0,-10.1,-9.9,-10.05,-10.02,-60.0,10.0,10.1,9.9,10.05,10.02,60.0]):
        rows.append({"record_key":f"r{index}","record_id":f"m{index}","canonical_smiles":f"C{'C'*index}","environment":"vacuum" if index<6 else "water","final_single_point_energy_Eh":energy,"composition_oof_residual_Eh":energy/10,"composition_robust_z":8 if index in {5,11} else .2,"atom_count":index+2,"element_counts":json.dumps({"C":index+1,"H":2}),"charge":0,"normal_termination":index!=0,"qc_status":"invalid_calculation" if index==0 else "passed_automated_checks","qc_flags":"abnormal_termination" if index==0 else ""})
    return pd.DataFrame(rows)


def test_complete_citation_and_export_metadata():
    assert "130 (22), 5819–5828" in ACS_CITATION
    assert all(name in ACS_CITATION for name in ["Zhu, J.","Zhou, J.","Sun, Z.","Huang, X.","Nie, Z."])
    assert "pages = {5819--5828}" in BIBTEX_CITATION
    metadata=prediction_metadata("model-x",{"target_definition":"ORCA FINAL SINGLE POINT ENERGY","target_unit":"Eh"})
    assert metadata["article_citation"]==ACS_CITATION and metadata["supporting_information_doi"].endswith("s001")
    assert metadata["software_version"]=="1.3.0" and metadata["model_id"]=="model-x"


def test_reversible_outlier_detection_and_bundle(tmp_path):
    original=_audit(); detected=detect_outliers(original,CleaningConfig(isolation_contamination=.1))
    assert detected.loc[0,"clearly_invalid"] and detected.statistical_suspect.any()
    keys=set(detected.loc[detected.clearly_invalid|detected.statistical_suspect,"record_key"])
    cleaned,excluded=apply_removal(detected,keys)
    assert len(cleaned)+len(excluded)==len(original) and len(original)==12
    paths=persist_cleaning_bundle(original,keys,tmp_path,CleaningConfig(isolation_contamination=.1))
    assert {path.name for path in paths.values()}=={"dataset_cleaned_v1.csv","excluded_records.csv","cleaning_report.json"}
    assert json.loads(paths["report"].read_text())["raw_orca_files_modified"] is False


def test_all_3d_styles_and_mol_export():
    mol,_=generate_conformer("C[N+](C)(C)C",42)
    for style in ["ball-and-stick","stick","sphere / space-filling","wireframe","cartoon-like","licorice / tube"]:
        figure=plotly_figure(mol,style=style,color_scheme="formal charge",background="gradient",labels="formal charge")
        assert len(figure.data)>0
    assert "V2000" in conformer_mol(mol)


def test_cleaning_page_renders_without_exception():
    from pathlib import Path
    from streamlit.testing.v1 import AppTest
    root=Path(__file__).parents[1]; audit=root/"data_qc"/"full_record_audit.csv"; created=not audit.exists()
    if created: audit.parent.mkdir(exist_ok=True); _audit().to_csv(audit,index=False)
    try:
        app=AppTest.from_file(str(root/"src"/"jpcb_energy"/"app.py"),default_timeout=30)
        app.query_params["page"]="Data Cleaning & Outlier Removal"; app.run()
        assert not app.exception
        initial=dict((metric.label,metric.value) for metric in app.metric); expected=initial["Clearly invalid"]
        next(button for button in app.button if button.label=="Remove Extreme Values").click(); app.run()
        assert dict((metric.label,metric.value) for metric in app.metric)["Excluded"]==expected
        next(button for button in app.button if button.label=="Undo").click(); app.run()
        assert dict((metric.label,metric.value) for metric in app.metric)["Excluded"]=="0"
    finally:
        if created: audit.unlink()
