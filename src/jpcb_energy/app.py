"""ZHU MolEnergy Workbench v1.4.0 local Streamlit application."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from uuid import uuid4

import pandas as pd
import plotly.express as px
import plotly.io as pio
import streamlit as st
import streamlit.components.v1 as components
from rdkit import Chem

from jpcb_energy.conformer import conformer_mol, conformer_png_bytes, conformer_rmsd, conformer_sdf, conformer_xyz, generate_conformers, plotly_figure
from jpcb_energy.data_cleaning import CleaningConfig, apply_removal, cleaning_report, compare_composition_models, detect_outliers
from jpcb_energy.descriptors import calculate_descriptors, calculate_rdkit_panel
from jpcb_energy.orca_parser import index_orca_folder
from jpcb_energy.provenance import ACS_CITATION, ARTICLE_AUTHORS, ARTICLE_DOI, ARTICLE_ISSUE, ARTICLE_PAGES, ARTICLE_TITLE, ARTICLE_URL, ARTICLE_VOLUME, BIBTEX_CITATION, PRODUCT_NAME, PRODUCT_SUBTITLE, SI_DOI, SI_URL, SOFTWARE_VERSION, add_prediction_metadata, prediction_workbook
from jpcb_energy.registry import discover_models
from jpcb_energy.user_training import train_user_model
from jpcb_energy.visualization import DrawSettings, molecule_png_bytes, molecule_properties, molecule_svg
from jpcb_energy.workbench import batch_predict, predict_with_bundle
from jpcb_energy.xtb import SUPPORTED_ALPB, detect_xtb, rdkit_optimize, run_xtb, save_xtb_path


ROOT = Path(__file__).resolve().parents[2]
USER_WORKSPACE = ROOT / "user_models"
XTB_JOBS = ROOT / "local_jobs" / "xtb"
CLEANING_JOBS = ROOT / "local_jobs" / "data_cleaning"
QC_ROOT = ROOT / "data_qc"
MASCOT_PATH = ROOT / "assets" / "zhu_molenergy_scientist.png"
EH_TO_EV = 27.211386245988

st.set_page_config(page_title=PRODUCT_NAME, page_icon="⚛", layout="wide", initial_sidebar_state="expanded")
st.markdown("""<style>
:root{--navy:#061827;--panel:#0B2B40;--blue:#075985;--cyan:#007F95;--coral:#C2413A;--ink:#102A43;--muted:#486581;--paper:#F4F8FB}
.stApp{background:linear-gradient(180deg,#F7FAFC 0%,#EDF4F8 100%);color:var(--ink)}
.block-container{max-width:1440px;padding-top:1.5rem;padding-bottom:3rem} h1{font-size:2rem!important;letter-spacing:-.02em} h2,h3{color:var(--navy)} p,li,span,label{line-height:1.5}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#071829,#0D2942)} [data-testid="stSidebar"] *{color:#E6F4FA!important}
[data-testid="stMetric"]{background:#FFFFFF;border:1px solid #D9E6EE;border-radius:12px;padding:1rem;box-shadow:0 3px 14px rgba(7,24,41,.05)}
[data-testid="stMetricLabel"]{color:#486581}[data-testid="stMetricValue"]{font-size:1.42rem!important;color:#071829;white-space:normal;overflow-wrap:anywhere}
.scientific-note{border-left:4px solid var(--cyan);background:#E8F7FA;padding:.85rem 1rem;border-radius:0 9px 9px 0;color:#16324A;margin:.6rem 0}
.coral-note{border-left-color:var(--coral);background:#FFF2EF}.chip{display:inline-block;padding:.18rem .55rem;margin:.1rem;border-radius:999px;background:#DDF3F7;color:#075B6A;font-size:.78rem;font-weight:650}.paper-source{font-size:.84rem;color:#38556B}
.section-kicker{color:#087E94;text-transform:uppercase;letter-spacing:.12em;font-size:.72rem;font-weight:800;margin-bottom:.2rem}
.hero{background:linear-gradient(120deg,#061827,#0B3D55);border-radius:18px;padding:1.4rem 1.6rem;color:#EAF9FC;box-shadow:0 12px 32px rgba(6,24,39,.14)}.hero h2{color:white;margin:.1rem 0}.hero p{color:#CFEAF1;margin:.25rem 0}.citation-card{background:#fff;border:1px solid #CFE2EA;border-radius:12px;padding:1rem 1.1rem}
.model-id{font-family:ui-monospace,SFMono-Regular,Consolas,monospace;overflow-wrap:anywhere;background:#EAF1F5;padding:.25rem .45rem;border-radius:5px;color:#102A43}
[data-testid="stWidgetLabel"],[data-testid="stWidgetLabel"] p,[role="tab"],.stTabs button,.stSelectbox label,.stSlider label,.stTextInput label{color:#102A43!important;opacity:1!important;font-weight:600}
[data-baseweb="select"]>div,[data-baseweb="input"]>div,input,textarea{background:#FFFFFF!important;color:#102A43!important;border-color:#9FB7C6!important}
.stButton>button,.stDownloadButton>button{border-radius:8px;font-weight:650;min-height:2.65rem}.stButton>button:focus,.stDownloadButton>button:focus{outline:3px solid rgba(0,127,149,.3)}
@media(max-width:900px){.block-container{padding-left:1rem;padding-right:1rem}[data-testid="column"]{min-width:100%!important}}
</style>""", unsafe_allow_html=True)


@lru_cache(maxsize=1)
def model_registry():
    return discover_models(ROOT)


@lru_cache(maxsize=8)
def cleaning_detection(path: str, mtime: float, config_values: tuple[float, ...]) -> pd.DataFrame:
    del mtime
    config=CleaningConfig(*config_values)
    return detect_outliers(pd.read_csv(path),config)


def model_picker(label: str = "Official model", key: str = "official_model"):
    registry = model_registry(); identifiers = list(registry)
    default = identifiers.index("v1.0.0-vacuum-reference") if "v1.0.0-vacuum-reference" in identifiers else 0
    model_id = st.selectbox(label, identifiers, index=default, key=key)
    st.markdown(f"<span class='model-id'>{model_id}</span>", unsafe_allow_html=True)
    return model_id, registry[model_id]


def nearest_record_text(result: dict) -> str:
    distance = result.get("nearest_neighbor_distance")
    formatted = "not available" if distance is None or pd.isna(distance) else f"{float(distance):.4f} standardized units"
    name = result.get("nearest_training_name") or "not available"
    return f"Nearest training record: **{name}** · distance **{formatted}**"


def model_summary(model_id: str, entry: dict):
    metadata=entry["metadata"]; validation=metadata.get("validation",{}).get("group_holdout",metadata.get("validation_metrics",{})); columns=st.columns(4)
    columns[0].metric("Environment",metadata.get("environment","vacuum")); columns[1].metric("Dielectric ε",str(metadata.get("dielectric_constant","not recorded"))); columns[2].metric("Validation MAE",f"{validation.get('mae_Eh',validation.get('test_mae_Eh',float('nan'))):.3f} Eh"); columns[3].metric("Model version",metadata.get("model_version","1.0.0"))
    with st.expander("Model identity and target definition"):
        st.markdown(f"Full model ID: <span class='model-id'>{model_id}</span>",unsafe_allow_html=True); st.write(metadata.get("target_definition","Target definition unavailable")); st.caption("The prediction is a model estimate of electronic energy, not a geometry optimization, ORCA calculation, or experimental measurement.")


def render_3d_html(molecule, **settings):
    figure=plotly_figure(molecule,**settings); auto_spin=settings.get("auto_spin",False)
    viewer_id=f"zhu_molenergy_3d_{uuid4().hex}"; html=pio.to_html(figure,include_plotlyjs=True,full_html=False,div_id=viewer_id,config={"displaylogo":False,"responsive":True,"scrollZoom":True,"modeBarButtonsToAdd":["resetCameraDefault3d","resetCameraLastSave3d"],"toImageButtonOptions":{"format":"png","filename":"zhu_molenergy_conformer","scale":2}})
    if auto_spin:
        html += f"""<script>(function(){{const gd=document.getElementById('{viewer_id}');let a=0;const timer=setInterval(function(){{if(!document.body.contains(gd)){{clearInterval(timer);return}}a+=0.018;Plotly.relayout(gd,{{'scene.camera.center':{{x:0,y:0,z:0}},'scene.camera.eye':{{x:1.8*Math.cos(a),y:1.8*Math.sin(a),z:1.05}}}})}},60);window.addEventListener('beforeunload',()=>clearInterval(timer),{{once:true}});}})();</script>"""
    if settings.get("background")=="gradient": html=f"<div style='border-radius:12px;background:linear-gradient(145deg,#F8FAFC,#CFFAFE);overflow:hidden'>{html}</div>"
    components.html(html,height=590,scrolling=False)


def prediction_downloads(frame: pd.DataFrame, model_id: str, metadata: dict, stem: str) -> None:
    enriched=add_prediction_metadata(frame,model_id,metadata); first,second=st.columns(2)
    first.download_button("Download CSV with provenance",enriched.to_csv(index=False),f"{stem}.csv","text/csv",use_container_width=True)
    second.download_button("Download Excel with provenance",prediction_workbook(frame,model_id,metadata),f"{stem}.xlsx","application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",use_container_width=True)


def copy_button(label: str, value: str, key: str) -> None:
    payload=json.dumps(value)
    components.html(f"""<button id="{key}" style="width:100%;padding:11px 16px;border:0;border-radius:8px;background:#007F95;color:white;font:600 15px sans-serif;cursor:pointer">{label}</button><div id="{key}_status" style="margin-top:7px;color:#38556B;font:13px sans-serif" aria-live="polite"></div><script>const b=document.getElementById('{key}'),s=document.getElementById('{key}_status'),t={payload};b.onclick=async()=>{{try{{await navigator.clipboard.writeText(t)}}catch(e){{const x=document.createElement('textarea');x.value=t;document.body.appendChild(x);x.select();document.execCommand('copy');x.remove()}}s.textContent='{label.replace('Copy','Copied')}.'}};</script>""",height=78)


def citation_copy_button() -> None:
    copy_button("Cite This Work", ACS_CITATION, "cite_work")


def empty_state(message: str) -> None:
    text,image=st.columns([.78,.22],vertical_alignment="center")
    text.info(message)
    if MASCOT_PATH.is_file(): image.image(str(MASCOT_PATH),use_container_width=True)


st.sidebar.markdown("## ⚛ ZHU MolEnergy"); st.sidebar.caption(PRODUCT_SUBTITLE); st.sidebar.markdown(f"<div class='paper-source'><b>Zhu et al.</b> <i>J. Phys. Chem. B</i> <b>2026</b>, <b>{ARTICLE_VOLUME}</b> ({ARTICLE_ISSUE}), {ARTICLE_PAGES}.<br><a href='{ARTICLE_URL}' target='_blank'>DOI: {ARTICLE_DOI}</a></div>",unsafe_allow_html=True)
pages=["Predict","Batch Screening","Molecular Explorer","Solvent Comparison","ORCA Workbench","Model Training","Data Quality","Data Cleaning & Outlier Removal","About & Citation"]
requested_page=st.query_params.get("page","Predict"); requested_page=requested_page if requested_page in pages else "Predict"
page=st.sidebar.radio("Workspace",pages,index=pages.index(requested_page)); st.sidebar.markdown("---")
with st.sidebar: citation_copy_button()
st.sidebar.caption("Localhost only · source data are never modified")
st.markdown(f"<div class='section-kicker'>{PRODUCT_NAME}</div>",unsafe_allow_html=True); st.title(page); st.caption(f"{PRODUCT_SUBTITLE} · Zhu et al., J. Phys. Chem. B 2026, {ARTICLE_VOLUME} ({ARTICLE_ISSUE}), {ARTICLE_PAGES}.")

if page == "Predict":
    hero_text=f"<div class='hero'><h2>Prediction with traceable scientific provenance</h2><p>Published descriptor-engineered models, interactive chemistry tools, and local-first workflows.</p><p>Zhu et al. <i>J. Phys. Chem. B</i> <b>2026</b>, <b>{ARTICLE_VOLUME}</b> ({ARTICLE_ISSUE}), {ARTICLE_PAGES}.</p></div>"
    hero_left,hero_right=st.columns([0.78,0.22],vertical_alignment="center"); hero_left.markdown(hero_text,unsafe_allow_html=True)
    if MASCOT_PATH.is_file(): hero_right.image(str(MASCOT_PATH),use_container_width=True)
    model_id,entry=model_picker(); model_summary(model_id,entry); smiles=st.text_input("SMILES","C=CC(=O)N",key="predict_smiles")
    current_signature=(model_id,smiles.strip())
    if st.button("Predict electronic energy",type="primary",key="predict_button"):
        try: st.session_state["prediction_result"]=predict_with_bundle(smiles,entry); st.session_state["prediction_signature"]=current_signature
        except Exception as exc: st.error(f"Prediction could not be completed: {exc}")
    result=st.session_state.get("prediction_result") if st.session_state.get("prediction_signature")==current_signature else None
    if st.session_state.get("prediction_result") is not None and result is None: st.info("The molecule or model changed. Run prediction again to refresh the result.")
    if result:
        left,right=st.columns([1.05,1.25],gap="large")
        with left:
            st.subheader("Molecular identity"); st.image(molecule_png_bytes(result["canonical_smiles"],settings=DrawSettings(width=680,height=430)),use_container_width=True); st.code(result["canonical_smiles"],language=None)
        with right:
            st.subheader("Model prediction"); first,second=st.columns(2); first.metric("Electronic energy",f"{result['prediction']:.6f} Eh",f"{result['prediction']*EH_TO_EV:.3f} eV",delta_color="off"); second.metric("GPR predictive SD",f"{result['predictive_std']:.6f} Eh",help="Native GPR standard deviation; not a calibrated confidence interval")
            status=result["applicability_status"]; st.markdown(f"<span class='chip'>{status.replace('_',' ').title()}</span>",unsafe_allow_html=True); st.markdown(nearest_record_text(result))
            if result.get("applicability_reasons"): st.warning("; ".join(result["applicability_reasons"]))
            with st.expander("Model input descriptors"): st.dataframe(pd.DataFrame([result["descriptors"]]).T.rename(columns={0:"value"}),use_container_width=True)
            export=pd.DataFrame([{"input_smiles":smiles,"canonical_smiles":result["canonical_smiles"],"predicted_E_sp_Eh":result["prediction"],"predictive_std_Eh":result["predictive_std"],"applicability_status":result["applicability_status"]}]); prediction_downloads(export,model_id,entry["metadata"],"zhu_molenergy_prediction")
        st.info("GPR uncertainty and applicability flags are screening diagnostics. They do not establish calculation accuracy for an out-of-domain structure.")
    st.markdown('<div class="scientific-note">Absolute electronic energy depends strongly on composition and atom count. Compare only chemically meaningful systems or a defined balanced reaction.</div>',unsafe_allow_html=True)

elif page == "Batch Screening":
    model_id,entry=model_picker(key="batch_model"); upload=st.file_uploader("CSV input · required column: smiles",type=["csv"]); chunk=st.number_input("Prediction chunk size",10,5000,500,10)
    if upload and st.button("Run screening",type="primary"):
        try:
            with st.spinner("Canonicalizing structures, calculating descriptors, and predicting…"): st.session_state["batch_result"],st.session_state["batch_summary"]=batch_predict(pd.read_csv(upload),entry,int(chunk)); st.session_state["batch_model_id"]=model_id
        except Exception as exc: st.error(f"Screening failed: {exc}")
    if "batch_result" in st.session_state and st.session_state.get("batch_model_id")==model_id:
        result,summary=st.session_state["batch_result"],st.session_state["batch_summary"]; columns=st.columns(6)
        for column,(name,value) in zip(columns,[("Valid",summary["valid_records"]),("Invalid",summary["invalid_records"]),("Duplicates",summary["duplicate_records"]),("Within",summary["within_domain"]),("Borderline",summary["borderline"]),("Outside",summary["outside_domain"])]): column.metric(name,value)
        sort=st.selectbox("Sort results",["predicted_E_sp_Eh","predictive_std_Eh","applicability_status"]); st.dataframe(result.sort_values(sort,na_position="last"),use_container_width=True,height=520); prediction_downloads(result,model_id,entry["metadata"],"zhu_molenergy_screening")
    elif "batch_result" in st.session_state: st.info("The model changed. Run screening again before downloading results.")

elif page == "Molecular Explorer":
    smiles=st.text_input("SMILES","CC[N+](C)(C)CCO",key="explorer_smiles")
    try: properties=molecule_properties(smiles); st.caption(f"{properties['formula']} · formal charge {properties['formal_charge']:+d} · exact mass {properties['exact_mass_Da']:.5f} Da · {properties['heavy_atoms']} heavy atoms")
    except Exception as exc: properties=None; st.error(str(exc))
    tabs=st.tabs(["2D viewer","3D conformers","Optimize geometry","Descriptors"])
    with tabs[0]:
        control,viewer=st.columns([0.36,0.64],gap="large")
        with control:
            style=st.selectbox("Structure expression",["standard 2D skeletal formula","atom-index annotated 2D","charge-highlighted 2D","heteroatom emphasis","aromatic ring emphasis","clean publication-style"]); overlay=st.multiselect("Additional overlays",["Atom indices","Atom maps","Formal charges"],default=[]); hydrogens=st.toggle("Show explicit hydrogens"); stereo=st.toggle("Stereo wedges",value=True); background=st.selectbox("Background",["white","transparent","dark"]); smarts=st.text_input("SMARTS highlight (optional)"); rotation=st.slider("2D rotation",-180,180,0,5); line_width=st.slider("Bond line width",1.0,5.0,2.0,.25); font_scale=st.slider("Atom/bond font scale",.6,1.8,1.0,.1); width=st.number_input("Canvas width",400,1600,720,40); height=st.number_input("Canvas height",300,1200,460,40); resolution=st.select_slider("PNG resolution",options=[1,2,3,4],value=2,format_func=lambda value:f"{value}×")
        if properties:
            settings=DrawSettings(style=style,atom_indices="Atom indices" in overlay or style=="atom-index annotated 2D",atom_maps="Atom maps" in overlay,show_hydrogens=hydrogens,stereo=stereo,highlight_charges="Formal charges" in overlay or style=="charge-highlighted 2D",highlight_heteroatoms=style=="heteroatom emphasis",highlight_aromatic=style=="aromatic ring emphasis",smarts=smarts,background=background,width=int(width),height=int(height),line_width=2.6 if style=="clean publication-style" else line_width,font_scale=font_scale,rotation=rotation)
            try:
                svg=molecule_svg(smiles,settings); png=molecule_png_bytes(smiles,settings=settings,scale=resolution)
                with viewer: st.image(svg,use_container_width=True); st.code(properties["isomeric_smiles"],language=None); first,second=st.columns(2); first.download_button("Export SVG",svg,"molecule.svg","image/svg+xml",use_container_width=True); second.download_button("Export PNG",png,"molecule.png","image/png",use_container_width=True)
            except Exception as exc: viewer.error(f"2D rendering failed: {exc}")
    with tabs[1]:
        controls,display=st.columns([0.34,0.66],gap="large")
        with controls:
            seed=st.number_input("ETKDG seed",0,2147483647,42,1); count=st.slider("Conformer count",1,20,5); force_field=st.selectbox("RDKit quick optimizer",["MMFF94","MMFF94s","UFF"]); style3d=st.selectbox("Representation",["ball-and-stick","stick","sphere / space-filling","wireframe","cartoon-like","licorice / tube"]); color3d=st.selectbox("Atom colors",["CPK","element pastel","formal charge","monochrome"]); background3d=st.selectbox("3D background",["light","dark","gradient","transparent"]); show_h3d=st.toggle("Show H in 3D",value=True); labels=st.selectbox("Atom labels",["none","element","index","element + index","formal charge"]); atom_scale=st.slider("Atom / sphere size",.5,2.2,1.0,.1); bond_width=st.slider("Bond / tube radius",1.0,14.0,5.0,.5); auto_spin=st.toggle("Rotation animation",help="Animation is presentation-only and does not change coordinates.")
            if st.button("Generate conformers",type="primary"):
                try:
                    with st.spinner("Embedding and force-field optimizing conformers…"): st.session_state["conformer_mols"],st.session_state["conformer_info"]=generate_conformers(smiles,int(seed),int(count),force_field); st.session_state["conformer_smiles"]=smiles.strip()
                except Exception as exc: st.error(f"Conformer generation failed: {exc}")
        molecules=st.session_state.get("conformer_mols") if st.session_state.get("conformer_smiles")==smiles.strip() else None
        if molecules:
            infos=st.session_state["conformer_info"]
            with display:
                st.success("Conformers are ranked by RDKit force-field energy; conformer #1 is the lowest-energy RDKit conformer.")
                selected=st.selectbox("Conformer ID",range(len(molecules)),format_func=lambda idx:f"#{infos[idx]['conformer']} (rank {idx+1}) · {infos[idx]['force_field_energy']:.4f} kcal/mol" if infos[idx]["force_field_energy"] is not None else f"#{infos[idx]['conformer']} (rank {idx+1})")
                render_3d_html(molecules[selected],style=style3d,color_scheme=color3d,background=background3d,show_hydrogens=show_h3d,labels=labels,atom_scale=atom_scale,bond_width=bond_width,auto_spin=auto_spin)
                rmsd=0.0 if selected==0 else conformer_rmsd(molecules[0],molecules[selected]); st.caption(f"Geometry source: {infos[selected]['geometry_source']} · RMSD to ranked conformer #1: {rmsd:.4f} Å")
                st.caption("Drag to rotate · wheel/pinch to zoom · double-click or use the camera reset control to auto-center and fit.")
                one,two,three,four=st.columns(4); one.download_button("SDF",conformer_sdf(molecules[selected]),"conformer.sdf","chemical/x-mdl-sdfile"); two.download_button("XYZ",conformer_xyz(molecules[selected]),"conformer.xyz","chemical/x-xyz"); three.download_button("MOL",conformer_mol(molecules[selected]),"conformer.mol","chemical/x-mdl-molfile"); four.download_button("PNG view",conformer_png_bytes(molecules[selected]),"conformer_3d.png","image/png")
                st.warning(infos[selected]["geometry_role"])
        else:
            with display: empty_state("Choose reproducible embedding settings and generate one or more conformers.")
    with tabs[2]:
        explicit=st.text_input("Optional existing xtb.exe path",key="xtb_path",help="The bundled runtime is detected first. A verified selection can be saved for future desktop launches."); installation=detect_xtb(explicit or None)
        if installation.available: st.success(f"Verified xTB: {installation.executable} · {installation.version} · source: {installation.source}")
        else: st.warning(installation.message); st.caption("The app checks its bundled runtime, your saved selection, PATH, and administrator-configured locations. WSL and Conda are not required.")
        if explicit and st.button("Verify and save xTB path"):
            saved_installation=save_xtb_path(explicit)
            if saved_installation.available: st.success(f"Saved verified xTB path in the per-user application configuration: {saved_installation.version}"); st.rerun()
            else: st.error(saved_installation.message)
        left,right=st.columns(2); seed_opt=left.number_input("Geometry seed",0,2147483647,42,1,key="opt_seed"); field_opt=right.selectbox("Fast local optimizer",["MMFF94","MMFF94s","UFF"])
        if st.button("Optimize with RDKit force field"):
            try: st.session_state["optimized_mol"],st.session_state["optimized_info"]=rdkit_optimize(smiles,int(seed_opt),field_opt); st.session_state["optimized_smiles"]=smiles.strip()
            except Exception as exc: st.error(str(exc))
        charge=int(properties["formal_charge"]) if properties else 0; c1,c2,c3,c4=st.columns(4); charge=c1.number_input("Formal charge",-10,10,charge); unpaired=c2.number_input("Unpaired electrons (--uhf)",0,10,0); solvent=c3.selectbox("xTB ALPB solvent",["none"]+sorted(SUPPORTED_ALPB)); opt_level=c4.selectbox("Optimization level",["normal","tight","verytight","extreme"]); threads=st.slider("xTB threads",1,8,1); confirm=st.checkbox("I have validated the charge and unpaired-electron count for this electronic state",value=unpaired==0)
        disabled=not installation.available or not properties or not confirm
        if st.button("Optimize with GFN2-xTB",type="primary",disabled=disabled):
            try:
                with st.spinner("Running isolated GFN2-xTB optimization and preserving the complete record…"): st.session_state["xtb_job"]=run_xtb(smiles,installation.executable or "",XTB_JOBS,int(charge),int(unpaired),None if solvent=="none" else solvent,seed=int(seed_opt),opt_level=opt_level,threads=int(threads)); st.session_state["xtb_smiles"]=smiles.strip()
            except Exception as exc: st.error(f"GFN2-xTB optimization failed: {exc}")
        if "optimized_mol" in st.session_state and st.session_state.get("optimized_smiles")==smiles.strip():
            st.subheader("RDKit optimized geometry"); render_3d_html(st.session_state["optimized_mol"],style="ball-and-stick",color_scheme="CPK",background="light",show_hydrogens=True,labels="none",atom_scale=1.0,bond_width=5.0,auto_spin=False); st.json(st.session_state["optimized_info"])
        if "xtb_job" in st.session_state and st.session_state.get("xtb_smiles")==smiles.strip():
            job=st.session_state["xtb_job"]; st.subheader("Complete xTB Results"); st.caption("GFN2-xTB semiempirical tight-binding result; this is not ORCA DFT and is not a GPR prediction.")
            if job.get("status")=="completed" and job.get("optimized_sdf"):
                before=Chem.MolFromMolFile(str(Path(job["optimized_sdf"]).with_name("input.sdf")),removeHs=False); after=Chem.MolFromMolFile(job["optimized_sdf"],removeHs=False); before_column,after_column=st.columns(2)
                with before_column: st.markdown("**RDKit input geometry**"); render_3d_html(before,style="ball-and-stick",color_scheme="CPK",background="light",show_hydrogens=True,labels="none",atom_scale=1.0,bond_width=5.0,auto_spin=False)
                with after_column: st.markdown("**GFN2-xTB optimized geometry**"); render_3d_html(after,style="ball-and-stick",color_scheme="CPK",background="light",show_hydrogens=True,labels="none",atom_scale=1.0,bond_width=5.0,auto_spin=False)
                e1,e2,e3=st.columns(3); e1.metric("Initial energy",f"{job['initial_energy_Eh']:.9f} Eh"); e2.metric("Final energy",f"{job['final_energy_Eh']:.9f} Eh"); e3.metric("Energy change",f"{job['energy_change_Eh']:.9f} Eh")
            st.write(f"**Status:** {job.get('status')} · **Converged:** {job.get('converged')} · **xTB:** {job.get('xtb_version')} · **Charge/UHF:** {job.get('charge')}/{job.get('unpaired_electrons')} · **Solvent:** {job.get('solvation_model')}")
            electronic=pd.DataFrame([{"property":key,"value":"Not reported by this calculation" if job.get(key) is None else job[key]} for key in ["homo_energy_eV","lumo_energy_eV","homo_lumo_gap_eV","fermi_level_eV","dipole_x_D","dipole_y_D","dipole_z_D","dipole_total_D","total_charge_e","final_gradient_norm_Eh_per_bohr","optimization_cycles","final_scc_iterations"]]); st.dataframe(electronic,use_container_width=True,hide_index=True)
            downloads=[("Complete job ZIP","job_zip","complete_xtb_job.zip","application/zip"),("Results JSON","results_json","xtb_results.json","application/json"),("Results CSV","results_csv","xtb_results.csv","text/csv"),("Raw log","raw_log","xtb.log","text/plain"),("HTML report","html_report","xtb_report.html","text/html"),("Optimized XYZ","optimized_xyz","xtbopt.xyz","chemical/x-xyz"),("Optimized SDF","optimized_sdf","optimized.sdf","chemical/x-mdl-sdfile"),("Optimized MOL","optimized_mol","optimized.mol","chemical/x-mdl-molfile")]
            columns=st.columns(4)
            for index,(label,key,name,mime) in enumerate(downloads):
                path=Path(job[key]) if job.get(key) else None
                if path and path.is_file(): columns[index%4].download_button(label,path.read_bytes(),name,mime,key=f"xtb_download_{key}")
            with st.expander("All structured xTB parameters"): st.json({key:value for key,value in job.items() if key not in {"xtbout_json","wiberg_bond_orders","atomic_partial_charges_e"}})
            with st.expander("Atomic charges and Wiberg bond orders"): st.json({"atomic_partial_charges_e":job.get("atomic_partial_charges_e"),"wiberg_bond_orders":job.get("wiberg_bond_orders")})
            with st.expander("Raw xTB output log"): st.code(Path(job["raw_log"]).read_text(encoding="utf-8",errors="replace"),language="text")
        st.markdown('<div class="scientific-note coral-note">GFN2-xTB/ALPB optimization is separate from ORCA CPCM reference calculations and never changes GPR inputs, labels, or official models.</div>',unsafe_allow_html=True)
    with tabs[3]:
        if properties:
            canonical,official=calculate_descriptors(smiles); _,panel=calculate_rdkit_panel(smiles); joined=pd.concat([pd.DataFrame({"descriptor":list(official),"value":list(official.values()),"role":"official GPR input"}),pd.DataFrame({"descriptor":list(panel),"value":list(panel.values()),"role":"exploratory property"})],ignore_index=True); st.dataframe(joined,use_container_width=True); st.download_button("Export descriptor CSV",joined.to_csv(index=False),"descriptors.csv","text/csv")

elif page == "Solvent Comparison":
    enhanced={key:value for key,value in model_registry().items() if key.startswith("v1.1.0")}; smiles=st.text_input("SMILES","C=CC(=O)N",key="solvent_smiles")
    if st.button("Compare environment-specific models",type="primary"):
        try:
            rows=[]
            for identifier,entry in enhanced.items():
                prediction=predict_with_bundle(smiles,entry); metadata=entry["metadata"]; rows.append({"model_id":identifier,"model_version":metadata.get("model_version","1.1.0"),"environment":metadata["environment"],"dielectric_constant":metadata["dielectric_constant"],"predicted_E_sp_Eh":prediction["prediction"],"predictive_std_Eh":prediction["predictive_std"],"applicability_status":prediction["applicability_status"],"article_doi":ARTICLE_DOI,"calculation_method":"Environment-specific GPR model using the published JPCB descriptor-engineering method"})
            st.session_state["solvent_frame"]=pd.DataFrame(rows).sort_values("dielectric_constant"); st.session_state["solvent_smiles_signature"]=smiles.strip()
        except Exception as exc: st.error(str(exc))
    if "solvent_frame" in st.session_state and st.session_state.get("solvent_smiles_signature")==smiles.strip():
        frame=st.session_state["solvent_frame"]; st.dataframe(frame,use_container_width=True); st.plotly_chart(px.line(frame,x="environment",y="predicted_E_sp_Eh",markers=True,labels={"predicted_E_sp_Eh":"Predicted electronic energy (Eh)"}),use_container_width=True); prediction_downloads(frame,"five-environment-comparison",{"model_version":"1.1.0","environment":"vacuum, ethanol, DMSO, water, formamide","target_definition":"Environment-specific ORCA FINAL SINGLE POINT ENERGY electronic energy","target_unit":"Eh"},"zhu_molenergy_solvent_comparison"); st.info("ORCA CPCM environments and xTB ALPB solvents are distinct models and are not treated as equivalent.")
    elif "solvent_frame" in st.session_state: st.info("The SMILES changed. Recompute the five-environment comparison before downloading.")

elif page == "ORCA Workbench":
    folder=st.text_input("Local folder containing ORCA .out files",help="Indexed recursively; source files are read-only and never modified.")
    if st.button("Index ORCA folder",type="primary"):
        try:
            path=Path(folder)
            if not path.is_dir(): raise ValueError("Select an existing local directory")
            with st.spinner("Parsing ORCA outputs…"): rows=index_orca_folder(path)
            for row in rows: row["frequencies_cm-1"]=json.dumps(row["frequencies_cm-1"])
            st.session_state["orca_manifest"]=pd.DataFrame(rows)
        except Exception as exc: st.error(str(exc))
    if "orca_manifest" in st.session_state:
        frame=st.session_state["orca_manifest"]; c1,c2,c3=st.columns(3); c1.metric("Files",len(frame)); c2.metric("Normal termination",int(frame.normal_termination.sum())); c3.metric("Imaginary modes",int((frame.imaginary_frequency_count>0).sum())); st.dataframe(frame,use_container_width=True,height=520); st.download_button("Export CSV",frame.to_csv(index=False),"orca_manifest.csv","text/csv"); st.download_button("Export JSON",frame.to_json(orient="records",indent=2),"orca_manifest.json","application/json")

elif page == "Model Training":
    st.warning("User-trained models remain isolated under user_models and cannot overwrite immutable official models."); upload=st.file_uploader("Training CSV with smiles and numeric target",type=["csv"])
    if upload:
        table=pd.read_csv(upload); target=st.selectbox("Target column",[column for column in table.columns if column!="smiles"]); unit=st.text_input("Target unit","user-defined"); family=st.selectbox("Model family",["GPR","SVR","Random Forest","ExtraTrees","Gradient Boosting","Ridge"])
        if st.button("Train group-aware model",type="primary"):
            try:
                with st.spinner("Training and validating by canonical structure group…"): path,metadata=train_user_model(table,target,unit,family,USER_WORKSPACE)
                st.success(f"Saved isolated model: {path}"); st.json(metadata)
            except Exception as exc: st.error(str(exc))

elif page == "Data Quality":
    st.warning("Local scientific quality-control workspace. Record-level source paths and reviewer decisions remain private and are not included in public distributions.")
    audit_path=QC_ROOT/"full_record_audit.csv"; summary_path=QC_ROOT/"qc_summary.json"
    if not audit_path.is_file(): empty_state("Run scripts/run_dft_qc.py with the project interpreter to build the read-only audit. No raw ORCA file is changed.")
    else:
        frame=pd.read_csv(audit_path); summary=json.loads(summary_path.read_text(encoding="utf-8")); columns=st.columns(4); columns[0].metric("Audited records",summary["records"]); columns[1].metric("Passed automated checks",summary["by_status"].get("passed_automated_checks",summary["by_status"].get("verified",0))); columns[2].metric("Needs human review",summary["by_status"].get("needs_review",0)); columns[3].metric("Invalid / unmatched",summary["by_status"].get("invalid_calculation",0)+summary["by_status"].get("unmatched",0))
        f1,f2,f3=st.columns(3); statuses=f1.multiselect("QC status",sorted(frame.qc_status.unique()),default=sorted(frame.qc_status.unique())); environments=f2.multiselect("Environment",sorted(frame.environment.unique()),default=sorted(frame.environment.unique())); search=f3.text_input("Record / molecule search")
        filtered=frame[frame.qc_status.isin(statuses)&frame.environment.isin(environments)]
        if search: filtered=filtered[filtered.record_id.str.contains(search,case=False,na=False)|filtered.smiles.str.contains(search,case=False,na=False)]
        st.dataframe(filtered[["record_key","smiles","qc_status","qc_flags","final_single_point_energy_Eh","minimum_frequency_cm-1","composition_robust_z"]],use_container_width=True,height=430)
        if len(filtered):
            key=st.selectbox("Record inspector",filtered.record_key.tolist()); record=filtered[filtered.record_key==key].iloc[0]; left,right=st.columns([.4,.6]); left.image(molecule_png_bytes(record.smiles),use_container_width=True); right.markdown(f"**Evidence**\n\n{record.evidence}"); right.code(record.frequency_output_path,language=None); right.json({"status":record.qc_status,"flags":record.qc_flags,"energy_Eh":record.final_single_point_energy_Eh,"minimum_frequency_cm-1":record["minimum_frequency_cm-1"],"composition_robust_z":record.composition_robust_z})
        plot=frame.dropna(subset=["composition_oof_residual_Eh"]); st.plotly_chart(px.scatter(plot,x="atom_count",y="composition_oof_residual_Eh",color="qc_status",facet_col="environment",facet_col_wrap=3,hover_name="record_id",labels={"atom_count":"Atoms including H","composition_oof_residual_Eh":"OOF composition residual (Eh)"}),use_container_width=True); st.caption("Residuals are out-of-fold estimates from element counts and formal charge. A large value is a review signal, not proof of an erroneous calculation.")
        st.download_button("Export sanitized QC summary",json.dumps(summary,indent=2),"sanitized_qc_summary.json","application/json")

elif page == "Data Cleaning & Outlier Removal":
    st.warning("This module excludes records only from a reversible working copy. It never deletes source rows, edits ORCA files, or overwrites published models.")
    audit_path=QC_ROOT/"full_record_audit.csv"
    if not audit_path.is_file(): empty_state("Run scripts/run_dft_qc.py first to build the read-only audit.")
    else:
        with st.expander("Detection thresholds",expanded=False):
            a,b,c=st.columns(3); iqr=a.number_input("IQR multiplier",1.0,5.0,1.5,.1); z=b.number_input("Z-score threshold",2.0,8.0,3.0,.1); mad=c.number_input("Modified Z-score (MAD)",2.0,8.0,3.5,.1)
            d,e=st.columns(2); contamination=d.slider("Isolation Forest expected fraction",.005,.10,.02,.005); composition=e.number_input("Composition-adjusted residual threshold",2.0,8.0,3.5,.1)
        config=CleaningConfig(iqr,z,mad,contamination,composition); detected=cleaning_detection(str(audit_path),audit_path.stat().st_mtime,(iqr,z,mad,contamination,composition))
        removed=set(st.session_state.get("cleaning_removed_keys",[])); history=list(st.session_state.get("cleaning_history",[])); cleaned,excluded=apply_removal(detected,removed)
        metrics=st.columns(5); metrics[0].metric("Original",len(detected)); metrics[1].metric("Clearly invalid",int(detected.clearly_invalid.sum())); metrics[2].metric("Statistical suspects",int(detected.statistical_suspect.sum())); metrics[3].metric("Working copy",len(cleaned)); metrics[4].metric("Excluded",len(excluded))
        st.markdown("**A. Clearly invalid** uses ORCA termination/convergence, charge, composition, protocol, substantive-frequency and inconsistent-duplicate evidence. **B. Statistical suspects** remain included until the user chooses to remove them.")
        candidate=detected[detected.clearly_invalid|detected.statistical_suspect]
        categories=st.multiselect("Filter anomaly category",["A: clearly invalid","B: statistical suspect"],default=["A: clearly invalid","B: statistical suspect"]); reasons=sorted({reason for value in candidate.outlier_reasons for reason in str(value).split(";") if reason}); reason_filter=st.multiselect("Filter detection reasons",reasons)
        filtered=candidate[candidate.outlier_category.isin(categories)];
        if reason_filter: filtered=filtered[filtered.outlier_reasons.map(lambda value:any(reason in str(value).split(";") for reason in reason_filter))]
        selected=st.multiselect("Select records for removal",filtered.record_key.astype(str).tolist(),format_func=lambda key:f"{key} · {filtered.set_index('record_key').loc[key,'outlier_category']}" if key in filtered.set_index('record_key').index else key)
        buttons=st.columns(6)
        def update_removed(new_keys: set[str]):
            st.session_state["cleaning_history"]=history+[sorted(removed)]; st.session_state["cleaning_removed_keys"]=sorted(new_keys)
        if buttons[0].button("Remove Extreme Values",use_container_width=True): update_removed(removed|set(detected.loc[detected.clearly_invalid,"record_key"].astype(str))); st.rerun()
        if buttons[1].button("Remove Suspected Outliers",use_container_width=True): update_removed(removed|set(detected.loc[detected.statistical_suspect,"record_key"].astype(str))); st.rerun()
        if buttons[2].button("Remove selected outliers",use_container_width=True,disabled=not selected): update_removed(removed|set(selected)); st.rerun()
        if buttons[3].button("Keep all",use_container_width=True): update_removed(set()); st.rerun()
        if buttons[4].button("Undo",use_container_width=True,disabled=not history): st.session_state["cleaning_removed_keys"]=history[-1]; st.session_state["cleaning_history"]=history[:-1]; st.rerun()
        if buttons[5].button("Restore Original Dataset",use_container_width=True): st.session_state["cleaning_removed_keys"]=[]; st.session_state["cleaning_history"]=[]; st.rerun()
        tab1,tab2,tab3,tab4=st.tabs(["Anomaly table","Distributions","Reasons","Model comparison"])
        with tab1: st.dataframe(filtered[["record_key","record_id","environment","final_single_point_energy_Eh","composition_oof_residual_Eh","qc_status","outlier_category","outlier_reasons"]],use_container_width=True,height=480)
        with tab2:
            left,right=st.columns(2); left.plotly_chart(px.box(detected,x="environment",y="final_single_point_energy_Eh",color="outlier_category",points="suspectedoutliers",title="Energy boxplots"),use_container_width=True); right.plotly_chart(px.histogram(detected,x="composition_oof_residual_Eh",color="outlier_category",nbins=70,title="Composition-adjusted residual distribution"),use_container_width=True)
            st.plotly_chart(px.scatter(detected,x="atom_count",y="composition_oof_residual_Eh",color="outlier_category",symbol="environment",hover_name="record_id",title="Flagged composition residuals"),use_container_width=True)
        with tab3:
            reason_rows=[{"reason":reason,"records":int(detected[reason].sum())} for reason in ["iqr_outlier","zscore_outlier","mad_outlier","isolation_forest_outlier","composition_residual_outlier","orca_qc_invalid","duplicate_inconsistent"]]; st.plotly_chart(px.bar(pd.DataFrame(reason_rows),x="reason",y="records",color="reason",title="Records by anomaly reason"),use_container_width=True)
        with tab4:
            st.caption("This is a group-aware Ridge composition baseline for sensitivity analysis, not the published JPCB GPR result.")
            if st.button("Train on cleaned dataset and compare original vs cleaned models",type="primary"):
                with st.spinner("Running group-aware diagnostic comparisons…"): st.session_state["cleaning_model_comparison"]=compare_composition_models(detected,removed)
            if "cleaning_model_comparison" in st.session_state: st.dataframe(st.session_state["cleaning_model_comparison"],use_container_width=True)
        report=cleaning_report(detected,cleaned,excluded,config,"interactive_working_copy")
        downloads=st.columns(3); downloads[0].download_button("Download dataset_cleaned_v1.csv",cleaned.to_csv(index=False),"dataset_cleaned_v1.csv","text/csv",use_container_width=True); downloads[1].download_button("Download excluded_records.csv",excluded.to_csv(index=False),"excluded_records.csv","text/csv",use_container_width=True); downloads[2].download_button("Download cleaning_report.json",json.dumps(report,indent=2),"cleaning_report.json","application/json",use_container_width=True)
        if st.button("Save reversible cleaning bundle locally"):
            stamp=pd.Timestamp.now().strftime("%Y%m%d_%H%M%S"); destination=CLEANING_JOBS/stamp; destination.mkdir(parents=True,exist_ok=False); cleaned.to_csv(destination/"dataset_cleaned_v1.csv",index=False); excluded.to_csv(destination/"excluded_records.csv",index=False); (destination/"cleaning_report.json").write_text(json.dumps(report,indent=2),encoding="utf-8"); st.success(f"Saved: {destination}")
        st.info("No performance value shown here replaces or revises the published JPCB model results. Any cleaned-dataset model is a separate user analysis.")

else:
    about_left,about_right=st.columns([.76,.24],vertical_alignment="center"); about_left.markdown(f"### {PRODUCT_NAME}"); about_left.caption(PRODUCT_SUBTITLE); about_left.markdown("This software is built on the scientific research and pretrained feature-engineered GPR models reported in the JPCB paper below.")
    if MASCOT_PATH.is_file(): about_right.image(str(MASCOT_PATH),use_container_width=True)
    st.subheader("Reference & Citation"); st.markdown(f"<div class='citation-card'><b>{ARTICLE_AUTHORS}.</b><br><b>{ARTICLE_TITLE}.</b><br><i>The Journal of Physical Chemistry B</i> <b>2026</b>, <b>{ARTICLE_VOLUME}</b> ({ARTICLE_ISSUE}), {ARTICLE_PAGES}.<br>DOI: <a href='{ARTICLE_URL}' target='_blank'>{ARTICLE_URL}</a><br>Supporting Information DOI: <a href='{SI_URL}' target='_blank'>{SI_URL}</a></div>",unsafe_allow_html=True)
    copy_left,copy_right=st.columns(2)
    with copy_left: copy_button("Copy Citation",ACS_CITATION,"copy_citation")
    with copy_right: copy_button("Copy BibTeX",BIBTEX_CITATION,"copy_bibtex")
    st.code(ACS_CITATION,language=None); st.code(BIBTEX_CITATION,language="bibtex")
    st.subheader("Research and model principle"); st.markdown("The published work uses chemically curated charged/polymerizable monomers, Mordred/RDKit molecular descriptors, feature selection, and Gaussian process regression to approximate ORCA-derived molecular electronic energies. The software preserves the released v1.0.0 reference model and v1.1.0 environment-specific bundles.")
    st.warning("Target-definition note: the paper introduction defines E_sp as final SCF electronic energy, whereas one Methods sentence mentions thermal corrections. Inspection of the released training table and ORCA labels shows that the distributed models predict ORCA FINAL SINGLE POINT ENERGY electronic energy. Existing labels were not silently changed.")
    st.subheader("Method boundaries"); st.markdown("- The JPCB paper is the scientific basis for the descriptor-engineered GPR prediction method and pretrained models.\n- RDKit conformers, interactive 3D visualization, GFN2-xTB optimization, workbench UI, and database-QC tooling are later software extensions, not original paper results.\n- xTB energy is never equated with the ORCA DFT target.\n- Absolute electronic energies should only be compared across chemically meaningful systems or a balanced reaction.")
    st.caption(f"Software version {SOFTWARE_VERSION} · GitHub POLY-MikeJ/JPCB-Single-Point-Energy-ML")
    st.subheader("Official model registry")
    for identifier,entry in model_registry().items():
        with st.expander(identifier,expanded=False): st.json(entry["metadata"])
