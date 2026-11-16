#!/usr/bin/env python
"""Build a read-only, record-level audit of the supplied ORCA datasets."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from jpcb_energy.data_qc import composition_oof_residuals, parse_geometry, read_text, reversible_inclusion, smiles_identity
from jpcb_energy.orca_parser import parse_orca


REPO = Path(__file__).resolve().parents[1]
WORKSPACE = REPO.parent
SOURCE = WORKSPACE / "计算数据"
TABLES = WORKSPACE / "代码及学习资料" / "0-JCP代码"
OUTPUT = REPO / "data_qc"


def robust_z(series: pd.Series) -> pd.Series:
    median=series.median(); mad=(series-median).abs().median()
    return (series-median)/(1.4826*mad) if mad and np.isfinite(mad) else pd.Series(0.0,index=series.index)


def truth(text: str, phrase: str) -> bool:
    return phrase.upper() in text.upper()


def audit_collection(collection: str, freq_root: Path, opt_root: Path, mapping: dict[str,str]) -> list[dict]:
    rows=[]
    for output in sorted(freq_root.glob("freq_outs_*/*.out")):
        environment=output.parent.name.removeprefix("freq_outs_"); record_id=output.stem; smiles=mapping.get(record_id)
        freq_input=freq_root/f"freq_inps_{environment}"/f"{record_id}.inp"; opt_input=opt_root/f"opt_inps_{environment}"/f"{record_id}.inp"; opt_output=opt_root/f"opt_outs_{environment}"/f"{record_id}.out"
        parsed=parse_orca(output); geometry=parse_geometry(freq_input) if freq_input.is_file() else {"geometry_charge":None,"geometry_multiplicity":None,"atom_count":None,"element_counts":{},"minimum_distance_A":None,"suspicious_contact":False}; identity=smiles_identity(smiles)
        opt_text=read_text(opt_output) if opt_output.is_file() else ""; flags=[]; category="normal"
        if smiles is None: flags.append("identity_unmatched")
        if not freq_input.is_file() or not opt_input.is_file() or not opt_output.is_file(): flags.append("missing_exact_pair")
        if not parsed["normal_termination"]: flags.append("frequency_job_abnormal_termination")
        if parsed["final_single_point_energy_Eh"] is None: flags.append("missing_final_single_point_energy")
        if parsed["task_type"]!="frequency": flags.append("task_mismatch")
        if parsed["method"]!="B3LYP" or parsed["basis_set"]!="6-311++G(d,p)": flags.append("method_or_basis_mismatch")
        if environment!="vacuum" and (parsed["solvent"]!=environment or parsed["dielectric_constant"] is None): flags.append("solvent_protocol_mismatch")
        if environment=="vacuum" and parsed["solvent"]!="vacuum": flags.append("solvent_protocol_mismatch")
        if identity["smiles_charge"] is not None and geometry["geometry_charge"]!=identity["smiles_charge"]: flags.append("formal_charge_mismatch")
        if identity["smiles_atom_count_with_H"] is not None and geometry["atom_count"]!=identity["smiles_atom_count_with_H"]: flags.append("atom_count_mismatch")
        if identity["smiles_element_counts"] and geometry["element_counts"]!=identity["smiles_element_counts"]: flags.append("element_composition_mismatch")
        if geometry["suspicious_contact"]: flags.append("suspicious_interatomic_contact")
        if opt_output.is_file() and not truth(opt_text,"ORCA TERMINATED NORMALLY"): flags.append("optimization_abnormal_termination")
        if opt_output.is_file() and not truth(opt_text,"THE OPTIMIZATION HAS CONVERGED"): flags.append("optimization_not_confirmed_converged")
        minimum=parsed["minimum_frequency_cm-1"]
        if minimum is not None and minimum < -50: flags.append("substantive_imaginary_frequency")
        elif minimum is not None and minimum < -1: flags.append("small_negative_frequency")
        hard={"frequency_job_abnormal_termination","missing_final_single_point_energy","task_mismatch","method_or_basis_mismatch","optimization_abnormal_termination"}
        if "identity_unmatched" in flags: status="unmatched"; category="identity"
        elif hard.intersection(flags): status="invalid_calculation"; category="computational_failure_or_identity"
        elif flags: status="needs_review"; category="protocol_geometry_or_frequency"
        else: status="verified"
        evidence=f"{output.name}: task={parsed['task_type']}; method={parsed['method']}; basis={parsed['basis_set']}; solvent={parsed['solvent']}; epsilon={parsed['dielectric_constant']}; normal={parsed['normal_termination']}; E={parsed['final_single_point_energy_Eh']} Eh; min_freq={minimum} cm^-1"
        rows.append({"record_key":f"{collection}:{environment}:{record_id}","collection":collection,"record_id":record_id,"smiles":smiles,"canonical_smiles":identity["canonical_smiles"],"environment":environment,"charge":parsed["charge"],"multiplicity":parsed["multiplicity"],"smiles_charge":identity["smiles_charge"],"method":parsed["method"],"basis_set":parsed["basis_set"],"task_type":parsed["task_type"],"dielectric_constant":parsed["dielectric_constant"],"normal_termination":parsed["normal_termination"],"optimization_converged":truth(opt_text,"THE OPTIMIZATION HAS CONVERGED") if opt_text else False,"final_single_point_energy_Eh":parsed["final_single_point_energy_Eh"],"energy_source":"last ORCA FINAL SINGLE POINT ENERGY; electronic Eh without ZPE/thermal correction","atom_count":geometry["atom_count"],"element_counts":json.dumps(geometry["element_counts"],sort_keys=True),"minimum_distance_A":geometry["minimum_distance_A"],"minimum_frequency_cm-1":minimum,"imaginary_frequency_count":parsed["imaginary_frequency_count"],"substantive_imaginary_count":sum(value < -50 for value in parsed["frequencies_cm-1"]),"frequency_count":len(parsed["frequencies_cm-1"]),"qc_status":status,"qc_category":category,"qc_flags":";".join(sorted(set(flags))),"evidence":evidence,"frequency_output_path":str(output.resolve()),"frequency_input_path":str(freq_input.resolve()),"optimization_output_path":str(opt_output.resolve()),"source_sha256":parsed["sha256"]})
    return rows


def main() -> None:
    if not SOURCE.is_dir(): raise FileNotFoundError(SOURCE)
    core=pd.read_csv(TABLES/"monomers_0404.csv"); library=pd.read_csv(TABLES/"library_0404.csv")
    core_map=dict(zip(core.name.astype(str),core.smiles.astype(str))); library_map=dict(zip(library.abbr.astype(str),library.smiles.astype(str)))
    rows=audit_collection("core_209",SOURCE/"ORCA-209 Molecules"/"209freq",SOURCE/"ORCA-209 Molecules"/"209opt",core_map)
    rows+=audit_collection("extended_791",SOURCE/"ORCA-791 Molecules"/"791freq",SOURCE/"ORCA-791 Molecules"/"791opt",library_map)
    frame=pd.DataFrame(rows); valid=frame.final_single_point_energy_Eh.notna() & frame.canonical_smiles.notna()
    frame["composition_oof_residual_Eh"]=np.nan; frame["composition_robust_z"]=np.nan
    for _,indices in frame[valid].groupby(["collection","environment"]).groups.items():
        subset=frame.loc[indices]; residuals=composition_oof_residuals(subset); frame.loc[indices,"composition_oof_residual_Eh"]=residuals; frame.loc[indices,"composition_robust_z"]=robust_z(residuals)
    statistical=frame.composition_robust_z.abs()>=6
    frame.loc[statistical & (frame.qc_status=="verified"),"qc_status"]="needs_review"
    frame.loc[statistical,"qc_flags"]=frame.loc[statistical,"qc_flags"].apply(lambda value: ";".join(filter(None,[value,"composition_residual_extreme_review_only"])))
    OUTPUT.mkdir(parents=True,exist_ok=True); decisions_path=OUTPUT/"review_decisions.csv"
    if decisions_path.is_file(): decisions=pd.read_csv(decisions_path)
    else: decisions=pd.DataFrame(columns=["record_key","review_decision","reproducible_reason","reviewed_by","reviewed_at"])
    inclusion=reversible_inclusion(frame,decisions)
    frame.to_csv(OUTPUT/"full_record_audit.csv",index=False); frame[frame.qc_status!="verified"].to_csv(OUTPUT/"suspect_records.csv",index=False); decisions.to_csv(decisions_path,index=False)
    inclusion[["record_key","collection","record_id","environment","qc_status","qc_flags","include_original_published","include_verified_strict","reviewed_by"]].to_csv(OUTPUT/"inclusion_manifest.csv",index=False)
    minimum_frequency=frame["minimum_frequency_cm-1"]
    summary={"generated_with":sys.version,"raw_sources_modified":False,"records":len(frame),"by_collection":frame.collection.value_counts().to_dict(),"by_environment":frame.environment.value_counts().to_dict(),"by_status":frame.qc_status.value_counts().to_dict(),"normal_termination":int(frame.normal_termination.sum()),"substantive_imaginary_records":int((frame.substantive_imaginary_count>0).sum()),"small_negative_only_records":int(((minimum_frequency<-1)&(minimum_frequency>=-50)).sum()),"protocol_mismatch_records":int(frame.qc_flags.str.contains("protocol_mismatch").sum()),"composition_extreme_review_records":int(statistical.sum()),"excluded_after_review":0,"policy":"Statistical extremes are review flags only. Raw data and original published inclusion are immutable."}
    (OUTPUT/"qc_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (OUTPUT/"sanitized_qc_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (OUTPUT/"DATA_DICTIONARY.md").write_text("""# DFT QC data dictionary\n\n- `record_key`: stable collection/environment/record identifier.\n- `qc_status`: verified, needs_review, invalid_calculation, unmatched, or excluded_after_review.\n- `qc_flags`: semicolon-separated reproducible evidence categories.\n- `composition_oof_residual_Eh`: group-fold out-of-fold residual from a Ridge reference using element counts and formal charge.\n- `composition_robust_z`: median/MAD-standardized residual within collection and environment; review signal only.\n- `include_original_published`: always true; the published/raw view is immutable.\n- `include_verified_strict`: reversible derived view excluding unmatched or explicitly invalid records, subject to review decisions.\n- Energy unit: Hartree (Eh); last ORCA `FINAL SINGLE POINT ENERGY`, without ZPE or thermal correction.\n""",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__": main()
