"""Citation and model-provenance metadata for public prediction exports."""

from __future__ import annotations

from io import BytesIO

import pandas as pd


PRODUCT_NAME = "ZHU MolEnergy Workbench"
PRODUCT_SUBTITLE = "Molecular Energy Prediction, Visualization & Computational Chemistry"
SOFTWARE_VERSION = "1.2.1"
ARTICLE_TITLE = "High-Throughput Prediction of Single-Point Energies for Charged Polymer Monomers through Feature-Engineered Machine Learning"
ARTICLE_AUTHORS = "Jie Zhu, Jing Zhou, Zhaoyan Sun, Xiayun Huang, and Zhihong Nie"
ARTICLE_JOURNAL = "The Journal of Physical Chemistry B"
ARTICLE_YEAR = "2026"
ARTICLE_DOI = "10.1021/acs.jpcb.6c02936"
ARTICLE_URL = f"https://doi.org/{ARTICLE_DOI}"
SI_DOI = "10.1021/acs.jpcb.6c02936.s001"
SI_URL = f"https://doi.org/{SI_DOI}"
ACS_CITATION = (
    "Zhu, J.; Zhou, J.; Sun, Z.; Huang, X.; Nie, Z. High-Throughput Prediction of "
    "Single-Point Energies for Charged Polymer Monomers through Feature-Engineered "
    "Machine Learning. J. Phys. Chem. B 2026. https://doi.org/10.1021/acs.jpcb.6c02936."
)
METHOD_NOTE = (
    "GPR prediction based on the published JPCB feature-engineered molecular-descriptor method. "
    "Released model labels are ORCA FINAL SINGLE POINT ENERGY electronic energies in Eh."
)


def prediction_metadata(model_id: str, metadata: dict) -> dict[str, str]:
    """Return explicit provenance fields for every downloadable prediction table."""
    return {
        "software_name": PRODUCT_NAME,
        "software_version": SOFTWARE_VERSION,
        "model_id": model_id,
        "model_version": str(metadata.get("model_version", "not recorded")),
        "model_environment": str(metadata.get("environment", "vacuum")),
        "calculation_method": METHOD_NOTE,
        "target_definition": str(metadata.get("target_definition", "not recorded")),
        "target_unit": str(metadata.get("target_unit", "Eh")),
        "article_doi": ARTICLE_DOI,
        "article_url": ARTICLE_URL,
    }


def add_prediction_metadata(frame: pd.DataFrame, model_id: str, metadata: dict) -> pd.DataFrame:
    output = frame.copy()
    for key, value in prediction_metadata(model_id, metadata).items():
        output[key] = value
    return output


def prediction_workbook(frame: pd.DataFrame, model_id: str, metadata: dict) -> bytes:
    """Build an XLSX with a results sheet plus a machine-readable provenance sheet."""
    enriched = add_prediction_metadata(frame, model_id, metadata)
    provenance = pd.DataFrame(
        [{"field": key, "value": value} for key, value in prediction_metadata(model_id, metadata).items()]
    )
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        enriched.to_excel(writer, sheet_name="predictions", index=False)
        provenance.to_excel(writer, sheet_name="provenance", index=False)
    return buffer.getvalue()
