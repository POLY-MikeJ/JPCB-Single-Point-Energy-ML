#!/usr/bin/env python
from __future__ import annotations
import importlib.metadata as metadata
import json
import platform
import subprocess
import sys
from pathlib import Path
import pandas as pd
import plotly.io as pio
from jpcb_energy.conformer import conformer_sdf, conformer_xyz, generate_conformer, plotly_figure
from jpcb_energy.orca_parser import parse_orca
from jpcb_energy.registry import discover_models
from jpcb_energy.visualization import molecule_png_bytes, molecule_svg
from jpcb_energy.workbench import predict_with_bundle

ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
OUT = ROOT / "validation_results" / "v1.1.0" / "qa"
OUT.mkdir(parents=True, exist_ok=True)

smiles = "CC[N+](C)(C)CCO"
(OUT / "charged_molecule_2d.svg").write_text(molecule_svg(smiles, atom_indices=True), encoding="utf-8")
(OUT / "charged_molecule_2d.png").write_bytes(molecule_png_bytes(smiles))
mol, conformer_info = generate_conformer(smiles, seed=42)
(OUT / "illustrative_conformer.sdf").write_text(conformer_sdf(mol), encoding="utf-8")
(OUT / "illustrative_conformer.xyz").write_text(conformer_xyz(mol), encoding="utf-8")
(OUT / "conformer_metadata.json").write_text(json.dumps(conformer_info, indent=2), encoding="utf-8")
pio.write_html(plotly_figure(mol), OUT / "illustrative_conformer_3d.html", include_plotlyjs=True, full_html=True, auto_open=False)

models = discover_models(ROOT)
predictions = []
for model_id, entry in models.items():
    result = predict_with_bundle("C=CC(=O)N", entry)
    predictions.append({"model_id": model_id, "environment": entry["metadata"].get("environment", "vacuum"), "dielectric_constant": entry["metadata"].get("dielectric_constant"), "prediction_Eh": result["prediction"], "predictive_std_Eh": result["predictive_std"], "applicability_status": result["applicability_status"]})
pd.DataFrame(predictions).to_csv(OUT / "multisolvent_prediction_example.csv", index=False)

calc = WORKSPACE / "计算数据" / "ORCA-209 Molecules" / "209freq"
paths = [calc / f"freq_outs_{env}" / "1VL-Bn.out" for env in ["vacuum", "ethanol", "dmso", "water", "formamide"]]
paths += [calc / "freq_outs_water" / f"{name}.out" for name in ["HEA", "HEMA"]]
rows = []
for path in paths:
    result = parse_orca(path); result["frequencies_cm-1"] = json.dumps(result["frequencies_cm-1"]); rows.append(result)
pd.DataFrame(rows).to_csv(OUT / "real_orca_parser_validation.csv", index=False)

test = subprocess.run([sys.executable, "-m", "pytest", "-q"], cwd=ROOT, text=True, capture_output=True)
(OUT / "test_report.txt").write_text(f"Command: {sys.executable} -m pytest -q\nExit code: {test.returncode}\n\nSTDOUT\n{test.stdout}\nSTDERR\n{test.stderr}\n", encoding="utf-8")
if test.returncode:
    raise SystemExit(test.returncode)

packages = ["numpy", "pandas", "scikit-learn", "joblib", "rdkit", "mordredcommunity", "streamlit", "plotly", "matplotlib", "pytest", "pillow"]
lines = [f"Platform: {platform.platform()}", f"Python: {platform.python_version()}", f"Executable: {sys.executable}"]
for package in packages:
    try: lines.append(f"{package}: {metadata.version(package)}")
    except metadata.PackageNotFoundError: lines.append(f"{package}: NOT INSTALLED")
(OUT / "environment_report.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
print(OUT)
