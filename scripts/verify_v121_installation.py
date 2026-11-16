#!/usr/bin/env python
"""Installed-environment smoke test for ZHU MolEnergy Workbench v1.2.1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from jpcb_energy.conformer import generate_conformers
from jpcb_energy.orca_parser import parse_orca
from jpcb_energy.provenance import ARTICLE_DOI, PRODUCT_NAME, SOFTWARE_VERSION, add_prediction_metadata
from jpcb_energy.registry import discover_models
from jpcb_energy.workbench import batch_predict, predict_with_bundle
from jpcb_energy.xtb import detect_xtb


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    models = discover_models(ROOT)
    reference = models["v1.0.0-vacuum-reference"]
    single = predict_with_bundle("C=CC(=O)N", reference)
    batch, summary = batch_predict(pd.DataFrame({"smiles": ["C=CC(=O)N", "CCO", "bad"]}), reference)
    solvents = {
        identifier: predict_with_bundle("C=CC(=O)N", entry)["prediction"]
        for identifier, entry in models.items()
        if identifier.startswith("v1.1.0")
    }
    conformers, metadata = generate_conformers("C=CC(=O)N", seed=42, count=2)
    parsed = parse_orca(ROOT / "tests" / "data" / "representative_output.txt")
    export = add_prediction_metadata(batch, "v1.0.0-vacuum-reference", reference["metadata"])
    xtb = detect_xtb()
    result = {
        "product": PRODUCT_NAME,
        "version": SOFTWARE_VERSION,
        "python": sys.version,
        "python_executable": sys.executable,
        "model_count": len(models),
        "reference_prediction_Eh": single["prediction"],
        "batch_valid": summary["valid_records"],
        "batch_invalid": summary["invalid_records"],
        "solvent_predictions_Eh": solvents,
        "conformers": len(conformers),
        "conformer_method": metadata[0]["method"],
        "orca_energy_Eh": parsed["final_single_point_energy_Eh"],
        "orca_normal_termination": parsed["normal_termination"],
        "export_article_doi": export.loc[0, "article_doi"],
        "citation_ok": export.loc[0, "article_doi"] == ARTICLE_DOI,
        "xtb_available": xtb.available,
        "xtb_version": xtb.version,
    }
    if len(models) != 6 or len(solvents) != 5 or not result["citation_ok"] or not parsed["normal_termination"]:
        raise RuntimeError(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
