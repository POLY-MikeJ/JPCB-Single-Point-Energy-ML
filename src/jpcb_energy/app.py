"""JPCB Energy Workbench v1.1 local Streamlit application."""
from __future__ import annotations
import json
from pathlib import Path
import pandas as pd
import streamlit as st
from jpcb_energy.conformer import conformer_sdf, conformer_xyz, generate_conformer, plotly_figure
from jpcb_energy.descriptors import calculate_descriptors, calculate_rdkit_panel
from jpcb_energy.orca_parser import index_orca_folder
from jpcb_energy.registry import discover_models
from jpcb_energy.user_training import train_user_model
from jpcb_energy.visualization import molecule_png_bytes, molecule_svg
from jpcb_energy.workbench import batch_predict, predict_with_bundle

ROOT = Path(__file__).resolve().parents[2]
USER_WORKSPACE = ROOT / "user_models"
st.set_page_config(page_title="JPCB Energy Workbench", page_icon="⚛", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>:root{--navy:#0B1F33;--blue:#1261A0;--cyan:#00A6C8}.stApp{background:linear-gradient(180deg,#F8FAFD 0%,#EEF4F9 100%)}h1,h2,h3{color:#0B1F33}[data-testid="stSidebar"]{background:#102A43}[data-testid="stSidebar"] *{color:#F2F7FA!important}.scientific-note{border-left:4px solid #00A6C8;background:#EAF7FA;padding:.8rem 1rem;border-radius:.3rem;color:#16324A}</style>""", unsafe_allow_html=True)

@st.cache_resource
def model_registry(): return discover_models(ROOT)

def model_picker(label="Official model"):
    registry = model_registry(); model_id = st.selectbox(label, list(registry), index=max(0, len(registry)-1)); return model_id, registry[model_id]

def model_summary(model_id, entry):
    meta=entry["metadata"]; cols=st.columns(4); cols[0].metric("Model ID",model_id); cols[1].metric("Environment",meta.get("environment","vacuum")); cols[2].metric("Dielectric ε",str(meta.get("dielectric_constant","not recorded"))); val=meta.get("validation",{}).get("group_holdout",meta.get("validation_metrics",{})); cols[3].metric("Validation MAE",f"{val.get('mae_Eh',val.get('test_mae_Eh',float('nan'))):.3f} Eh"); st.caption(meta.get("target_definition","Target definition unavailable"))

st.sidebar.title("JPCB Energy Workbench"); st.sidebar.caption("v1.1.0 · local CPU workflow")
page=st.sidebar.radio("Workspace",["Predict","Batch Screening","Molecular Explorer","Solvent Comparison","ORCA Workbench","Model Training","Model & Documentation"])
st.sidebar.markdown("---"); st.sidebar.caption("All molecular processing remains on this computer."); st.title(page)

if page=="Predict":
    model_id,entry=model_picker(); model_summary(model_id,entry); smiles=st.text_input("SMILES","C=CC(=O)N")
    if st.button("Predict energy",type="primary",use_container_width=True):
        try:
            result=predict_with_bundle(smiles,entry); left,right=st.columns([1,1.2]); left.image(molecule_png_bytes(result["canonical_smiles"]),caption=result["canonical_smiles"]); right.metric("Predicted E_sp",f"{result['prediction']:.6f} Eh"); right.metric("GPR predictive standard deviation",f"{result['predictive_std']:.6f} Eh"); right.metric("Applicability",result["applicability_status"]); right.write("Nearest training record:",result.get("nearest_training_name","not available"),result.get("nearest_neighbor_distance",""));
            if result.get("applicability_reasons"): right.warning("; ".join(result["applicability_reasons"]))
            with st.expander("Model input descriptors"): st.dataframe(pd.DataFrame([result["descriptors"]]).T.rename(columns={0:"value"}),use_container_width=True)
            st.info("The GPR standard deviation is not a calibrated confidence interval. Applicability flags are screening diagnostics, not proof of accuracy.")
        except Exception as exc: st.error(str(exc))
    st.markdown('<div class="scientific-note">Absolute electronic energy is composition- and atom-count-dependent. Meaningful energetic comparisons require chemically comparable systems or a defined balanced reaction.</div>',unsafe_allow_html=True)

elif page=="Batch Screening":
    model_id,entry=model_picker(); upload=st.file_uploader("CSV input (required column: smiles)",type=["csv"]); chunk=st.number_input("Prediction chunk size",10,5000,500,10)
    if upload and st.button("Run screening",type="primary"):
        try:
            with st.spinner("Calculating descriptors and predicting..."): result,summary=batch_predict(pd.read_csv(upload),entry,int(chunk))
            st.session_state["batch_result"],st.session_state["batch_summary"]=result,summary
        except Exception as exc: st.error(str(exc))
    if "batch_result" in st.session_state:
        result,summary=st.session_state["batch_result"],st.session_state["batch_summary"]; cols=st.columns(6)
        for col,(name,value) in zip(cols,[("Valid",summary["valid_records"]),("Invalid",summary["invalid_records"]),("Duplicates",summary["duplicate_records"]),("Within",summary["within_domain"]),("Borderline",summary["borderline"]),("Outside",summary["outside_domain"])]): col.metric(name,value)
        sort=st.selectbox("Sort",["predicted_E_sp_Eh","predictive_std_Eh","applicability_status"]); st.dataframe(result.sort_values(sort,na_position="last"),use_container_width=True,height=520); st.download_button("Download full CSV",result.to_csv(index=False),"screening_results.csv","text/csv"); st.caption(f"Processed in {summary['elapsed_seconds']:.2f} s; each canonical structure was featurized once and estimator prediction was batched.")

elif page=="Molecular Explorer":
    smiles=st.text_input("SMILES","CC[N+](C)(C)CCO"); atom_indices=st.checkbox("Show atom indices"); highlight=st.checkbox("Highlight formal charges",value=True)
    if st.button("Explore molecule",type="primary"):
        try:
            canonical,model_desc=calculate_descriptors(smiles); _,panel=calculate_rdkit_panel(smiles); tabs=st.tabs(["2D","Illustrative 3D","Descriptors"])
            with tabs[0]:
                svg=molecule_svg(canonical,atom_indices,highlight); st.image(svg); st.download_button("Download SVG",svg,"molecule.svg","image/svg+xml"); st.download_button("Download PNG",molecule_png_bytes(canonical),"molecule.png","image/png")
            with tabs[1]:
                mol,info=generate_conformer(canonical,42); st.plotly_chart(plotly_figure(mol),use_container_width=True); st.warning(info["geometry_role"]); st.json(info); c1,c2=st.columns(2); c1.download_button("Download SDF",conformer_sdf(mol),"illustrative_conformer.sdf","chemical/x-mdl-sdfile"); c2.download_button("Download XYZ",conformer_xyz(mol),"illustrative_conformer.xyz","chemical/x-xyz")
            with tabs[2]:
                joined=pd.concat([pd.DataFrame({"descriptor":list(model_desc),"value":list(model_desc.values()),"role":"official model input"}),pd.DataFrame({"descriptor":list(panel),"value":list(panel.values()),"role":"exploratory only"})],ignore_index=True); st.dataframe(joined,use_container_width=True); st.download_button("Download descriptors",joined.to_csv(index=False),"descriptors.csv","text/csv")
        except Exception as exc: st.error(str(exc))

elif page=="Solvent Comparison":
    enhanced={k:v for k,v in model_registry().items() if k.startswith("v1.1.0")}; smiles=st.text_input("SMILES","C=CC(=O)N")
    if st.button("Compare environments",type="primary"):
        try:
            rows=[]
            for model_id,entry in enhanced.items():
                result=predict_with_bundle(smiles,entry); meta=entry["metadata"]; rows.append({"model_id":model_id,"environment":meta["environment"],"dielectric_constant":meta["dielectric_constant"],"predicted_E_sp_Eh":result["prediction"],"predictive_std_Eh":result["predictive_std"],"applicability_status":result["applicability_status"]})
            frame=pd.DataFrame(rows).sort_values("dielectric_constant"); st.dataframe(frame,use_container_width=True); st.line_chart(frame.set_index("environment")["predicted_E_sp_Eh"]); st.download_button("Download comparison",frame.to_csv(index=False),"solvent_comparison.csv","text/csv"); st.info("Compare solvent response only for the same molecular composition. These absolute total electronic energies are not reaction energies.")
        except Exception as exc: st.error(str(exc))

elif page=="ORCA Workbench":
    folder=st.text_input("Local folder containing ORCA .out files",help="Files are indexed recursively and never modified.")
    if st.button("Index folder",type="primary"):
        try:
            path=Path(folder)
            if not path.is_dir(): raise ValueError("Select an existing local directory")
            with st.spinner("Parsing ORCA outputs..."): rows=index_orca_folder(path)
            for row in rows: row["frequencies_cm-1"]=json.dumps(row["frequencies_cm-1"])
            st.session_state["orca_manifest"]=pd.DataFrame(rows)
        except Exception as exc: st.error(str(exc))
    if "orca_manifest" in st.session_state:
        frame=st.session_state["orca_manifest"]; c1,c2,c3=st.columns(3); c1.metric("Files",len(frame)); c2.metric("Normal termination",int(frame.normal_termination.sum())); c3.metric("Imaginary modes",int((frame.imaginary_frequency_count>0).sum())); st.dataframe(frame,use_container_width=True,height=520); st.download_button("Export CSV",frame.to_csv(index=False),"orca_manifest.csv","text/csv"); st.download_button("Export JSON",frame.to_json(orient="records",indent=2),"orca_manifest.json","application/json")

elif page=="Model Training":
    st.warning("User-trained models are isolated under user_models and never overwrite immutable official models."); upload=st.file_uploader("Training CSV with smiles and a numeric target",type="csv")
    if upload:
        table=pd.read_csv(upload); target=st.selectbox("Target column",[c for c in table.columns if c!="smiles"]); unit=st.text_input("Target unit","user-defined"); family=st.selectbox("Model family",["GPR","SVR","Random Forest","ExtraTrees","Gradient Boosting","Ridge"]); st.caption("Small datasets have high validation uncertainty. At least 20 valid records and 10 unique canonical structures are required.")
        if st.button("Train group-aware model",type="primary"):
            try:
                with st.spinner("Training and validating..."): path,metadata=train_user_model(table,target,unit,family,USER_WORKSPACE)
                st.success(f"Saved isolated model: {path}"); st.json(metadata)
            except Exception as exc: st.error(str(exc))

else:
    st.subheader("Official model registry")
    for model_id,entry in model_registry().items():
        with st.expander(model_id,expanded=model_id.startswith("v1.1.0")): st.json(entry["metadata"])
    st.subheader("Scientific scope"); st.markdown("The fixed v1.0.0 model remains unchanged. v1.1.0 models use the same eight graph descriptors and environment-specific electronic energies. The 3D explorer is illustrative and is not part of model input generation."); st.link_button("Published article","https://doi.org/10.1021/acs.jpcb.6c02936"); st.caption("Code: MIT license. Research data licensing is separate.")
