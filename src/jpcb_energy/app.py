"""Local Streamlit interface."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from jpcb_energy.prediction import predict_batch, predict_one
from jpcb_energy.visualization import molecule_image

ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "models"

st.set_page_config(page_title="JPCB Single-Point Energy ML", page_icon="⚛", layout="wide")
st.title("Single-Point Energy Prediction for Polymer Monomers")
st.caption("Local, CPU-only inference using the published eight-descriptor GPR workflow")

single, batch, info = st.tabs(["Single molecule", "Batch CSV", "Model information"])
with single:
    smiles = st.text_input("SMILES", "C=CC(=O)N")
    if st.button("Predict", type="primary"):
        try:
            result = predict_one(smiles, MODEL_DIR)
            left, right = st.columns([1, 1])
            left.image(molecule_image(result["canonical_smiles"]), caption=result["canonical_smiles"])
            right.metric("Predicted E_sp", f"{result['prediction']:.6f} {result['unit']}")
            right.write(f"GPR predictive standard deviation: {result['predictive_std']:.6f} Eh")
            right.warning("The predictive standard deviation is not a calibrated confidence interval.")
            with st.expander("Eight descriptors"):
                st.dataframe(pd.DataFrame([result["descriptors"]]).T.rename(columns={0: "value"}))
        except Exception as exc:
            st.error(str(exc))
with batch:
    upload = st.file_uploader("Upload a CSV containing a smiles column", type="csv")
    if upload is not None:
        try:
            result = predict_batch(pd.read_csv(upload), MODEL_DIR)
            st.dataframe(result)
            st.download_button("Download predictions", result.to_csv(index=False), "predictions.csv", "text/csv")
        except Exception as exc:
            st.error(str(exc))
with info:
    st.markdown(
        """The model is intended for curated, closed-shell, polar or charged polymerizable monomers.
Predictions for metals, radicals, zwitterions, explicit ion pairs, oligomers, and structures outside the
training descriptor space require independent quantum-chemical validation. All processing is local."""
    )
    st.link_button("Published article", "https://doi.org/10.1021/acs.jpcb.6c02936")

