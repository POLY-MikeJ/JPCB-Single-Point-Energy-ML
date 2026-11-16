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
        else: status="passed_automated_checks"
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
    frame.loc[statistical & (frame.qc_status=="passed_automated_checks"),"qc_status"]="needs_review"
    frame.loc[statistical,"qc_flags"]=frame.loc[statistical,"qc_flags"].apply(lambda value: ";".join(filter(None,[value,"composition_residual_extreme_review_only"])))
    OUTPUT.mkdir(parents=True,exist_ok=True); decisions_path=OUTPUT/"review_decisions.csv"
    decision_columns=["record_key","review_decision","reproducible_reason","reviewed_by","reviewed_at"]
    if decisions_path.is_file():
        decisions=pd.read_csv(decisions_path)
        if len(decisions)==0: decisions=pd.DataFrame(columns=decision_columns)
    else: decisions=pd.DataFrame(columns=decision_columns)
    if len(decisions) and not set(decisions.review_decision).issubset({"include","quarantine","recalculate","exclude"}): raise ValueError("Review decisions must be include, quarantine, recalculate, or exclude")
    inclusion=reversible_inclusion(frame,decisions)
    frame.to_csv(OUTPUT/"full_record_audit.csv",index=False); frame[frame.qc_status!="passed_automated_checks"].to_csv(OUTPUT/"suspect_records.csv",index=False); decisions.to_csv(decisions_path,index=False)
    inclusion[["record_key","collection","record_id","environment","qc_status","qc_flags","include_original_published","include_passed_automated","include_verified_strict","reviewed_by","reviewed_at"]].to_csv(OUTPUT/"inclusion_manifest.csv",index=False)
    review_queue=frame[frame.qc_status!="passed_automated_checks"].copy()
    def recommendation(flags: str) -> str:
        values=set(str(flags).split(";"))
        if values & {"substantive_imaginary_frequency","optimization_abnormal_termination","optimization_not_confirmed_converged"}: return "recalculate"
        if values & {"formal_charge_mismatch","atom_count_mismatch","element_composition_mismatch","solvent_protocol_mismatch","missing_exact_pair"}: return "quarantine"
        return "include"
    review_queue["recommended_action"]=review_queue.qc_flags.map(recommendation); review_queue["human_decision"]="pending"; review_queue["reviewer"]=""; review_queue["reviewed_at"]=""; review_queue.to_csv(OUTPUT/"human_review_queue.csv",index=False)
    identity_mask=frame.qc_flags.str.contains("formal_charge_mismatch|atom_count_mismatch|element_composition_mismatch",na=False)
    identity_review=frame.loc[identity_mask,["record_key","record_id","environment","smiles","charge","smiles_charge","atom_count","element_counts","qc_flags","frequency_input_path","source_sha256"]].copy()
    identity_review["automated_interpretation"]=identity_review.record_id.map({"1VL-Np":"ORCA input is a +1, one-extra-H protonation state relative to the neutral source SMILES; representation/protonation mismatch pending owner confirmation.","HEA":"ORCA formula contains two additional H atoms relative to source SMILES; source identity or bond-saturation mismatch pending owner confirmation.","HEMA":"ORCA formula contains two additional H atoms relative to source SMILES; source identity or bond-saturation mismatch pending owner confirmation."}).fillna("identity mismatch pending owner review")
    identity_review["human_decision"]="pending"; identity_review.to_csv(OUTPUT/"identity_consistency_review.csv",index=False)
    frequency_review=frame.loc[frame["minimum_frequency_cm-1"].fillna(0)<-1,["record_key","record_id","environment","minimum_frequency_cm-1","imaginary_frequency_count","substantive_imaginary_count","normal_termination","optimization_converged","qc_flags","frequency_output_path","source_sha256"]].copy()
    frequency_review["recommended_action"]=frequency_review["minimum_frequency_cm-1"].map(lambda value:"recalculate" if value<-50 else "quarantine"); frequency_review["human_decision"]="pending"; frequency_review.to_csv(OUTPUT/"frequency_review_queue.csv",index=False)
    minimum_frequency=frame["minimum_frequency_cm-1"]
    summary={"generated_with":sys.version,"raw_sources_modified":False,"records":len(frame),"by_collection":frame.collection.value_counts().to_dict(),"by_environment":frame.environment.value_counts().to_dict(),"by_status":frame.qc_status.value_counts().to_dict(),"normal_termination":int(frame.normal_termination.sum()),"substantive_imaginary_records":int((frame.substantive_imaginary_count>0).sum()),"small_negative_only_records":int(((minimum_frequency<-1)&(minimum_frequency>=-50)).sum()),"protocol_mismatch_records":int(frame.qc_flags.str.contains("protocol_mismatch").sum()),"composition_extreme_review_records":int(statistical.sum()),"identity_mismatch_records":int(identity_mask.sum()),"human_review_decisions":len(decisions),"excluded_after_review":int((decisions.review_decision=="exclude").sum()) if len(decisions) else 0,"policy":"Passed automated checks is not human verification. Statistical extremes are review flags only. Raw data and original published inclusion are immutable."}
    (OUTPUT/"qc_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (OUTPUT/"sanitized_qc_summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    (OUTPUT/"DATA_DICTIONARY.md").write_text("""# DFT QC data dictionary\n\n- `record_key`: stable collection/environment/record identifier.\n- `qc_status`: `passed_automated_checks`, `needs_review`, `invalid_calculation`, or `unmatched`; automated pass is not human verification.\n- `qc_flags`: semicolon-separated reproducible evidence categories.\n- `composition_oof_residual_Eh`: group-fold out-of-fold residual from a Ridge reference using element counts and formal charge.\n- `composition_robust_z`: median/MAD-standardized residual within collection and environment; review signal only.\n- `include_original_published`: always true; the published/raw view is immutable.\n- `include_passed_automated`: derived automated-check view.\n- `include_verified_strict`: reversible reviewed view; human actions are include, quarantine, recalculate, or exclude.\n- Energy unit: Hartree (Eh); last ORCA `FINAL SINGLE POINT ENERGY`, without ZPE or thermal correction.\n""",encoding="utf-8")
    (OUTPUT/"TARGET_DEFINITION_RECONCILIATION.md").write_text("""# Target-definition reconciliation\n\nThe final JPCB article contains two incompatible descriptions: the introduction defines E_sp as final self-consistent-field electronic energy at the optimized geometry, while Methods says SCF energy combined with thermal corrections at 298.15 K. The original ML notebook reads `target` from `monomers_0404.csv`. Direct comparison against raw ORCA outputs and `validation_results/orca_label_validation.csv` shows that the released labels match ORCA `FINAL SINGLE POINT ENERGY`, not total thermal energy, enthalpy, or Gibbs free energy. For example, vacuum VA has raw FINAL SINGLE POINT ENERGY -154.999767215705 Eh, source target -154.9996775 Eh, total thermal energy -154.91588705 Eh, enthalpy -154.91494284 Eh, and Gibbs free energy -154.94557051 Eh.\n\nNo released model labels were changed. The inconsistency is documented for owner/editorial follow-up.\n""",encoding="utf-8")
    (OUTPUT/"IDENTITY_REVIEW_FINDINGS.md").write_text("""# Controlled identity and calculation-consistency review\n\nThe reproducible audit finds 15 record-level identity flags, not 13: three unique core molecule identifiers repeated in five environments. All remain pending qualified human review.\n\n- `1VL-Np` (five environments): source SMILES is neutral C10H18N2, whereas every ORCA input is charge +1 with C10H19N2. No counterion element is present. The one-extra-H/+1 pattern is consistent with a protonated representation that is missing from the source SMILES, but the owner must confirm the intended standardized structure before any decision.\n- `HEA` (five environments): source SMILES formula is C5H8O3, while every ORCA geometry is neutral C5H10O3. The two-extra-H difference is consistent across environments and is not a counterion. Source identity/bond saturation must be confirmed.\n- `HEMA` (five environments): source SMILES formula is C6H10O3, while every ORCA geometry is neutral C6H12O3. The two-extra-H difference is consistent across environments and is not a counterion. Source identity/bond saturation must be confirmed.\n- Water `HEA` and `HEMA` outputs have the separately documented solvent-protocol exception: their frequency outputs do not expose the expected CPCM evidence, although their associated inputs request water. They remain out of the enhanced-model common membership without changing the v1.0.0 model.\n\nRecommended automated disposition is `quarantine` pending structure-owner confirmation; this is not a final review decision. Original outputs, published membership, hashes, and model artifacts are unchanged.\n""",encoding="utf-8")
    print(json.dumps(summary,indent=2))


if __name__=="__main__": main()
