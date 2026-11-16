"""Read-only, reproducible scientific QC helpers for supplied ORCA data."""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
from rdkit import Chem
from sklearn.linear_model import Ridge
from sklearn.model_selection import GroupKFold


XYZ_BLOCK = re.compile(r"^\s*(?:\|\s*\d+>\s*)?\*\s*xyz(?:file)?\s+(-?\d+)\s+(\d+)\s*$([\s\S]*?)^\s*(?:\|\s*\d+>\s*)?\*\s*$", re.M | re.I)
ATOM_LINE = re.compile(r"^\s*(?:\|\s*\d+>\s*)?([A-Z][a-z]?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)\s+(-?\d+(?:\.\d+)?)", re.M)


def read_text(path: Path) -> str:
    raw=path.read_bytes(); encoding="utf-16" if raw.startswith((b"\xff\xfe",b"\xfe\xff")) else "utf-8"; return raw.decode(encoding,errors="replace")


def parse_geometry(path: Path) -> dict:
    blocks=XYZ_BLOCK.findall(read_text(path))
    if not blocks: return {"geometry_charge":None,"geometry_multiplicity":None,"atom_count":None,"element_counts":{},"minimum_distance_A":None,"suspicious_contact":False}
    charge,multiplicity,body=blocks[-1]; atoms=[(symbol,np.array([float(x),float(y),float(z)])) for symbol,x,y,z in ATOM_LINE.findall(body)]
    distances=[float(np.linalg.norm(first[1]-second[1])) for idx,first in enumerate(atoms) for second in atoms[idx+1:]]; minimum=min(distances) if distances else None
    return {"geometry_charge":int(charge),"geometry_multiplicity":int(multiplicity),"atom_count":len(atoms),"element_counts":dict(Counter(atom[0] for atom in atoms)),"minimum_distance_A":minimum,"suspicious_contact":minimum is not None and minimum<0.55}


def smiles_identity(smiles: str | None) -> dict:
    molecule=Chem.MolFromSmiles(str(smiles)) if smiles and str(smiles)!="nan" else None
    if molecule is None: return {"canonical_smiles":None,"smiles_charge":None,"smiles_atom_count_with_H":None,"smiles_element_counts":{}}
    with_h=Chem.AddHs(molecule)
    return {"canonical_smiles":Chem.MolToSmiles(molecule,canonical=True,isomericSmiles=True),"smiles_charge":int(Chem.GetFormalCharge(molecule)),"smiles_atom_count_with_H":with_h.GetNumAtoms(),"smiles_element_counts":dict(Counter(atom.GetSymbol() for atom in with_h.GetAtoms()))}


def composition_oof_residuals(frame: pd.DataFrame) -> pd.Series:
    elements=sorted({element for value in frame.element_counts for element in json.loads(value or "{}").keys()})
    X=np.array([[json.loads(value or "{}").get(element,0) for element in elements]+[0 if pd.isna(charge) else charge] for value,charge in zip(frame.element_counts,frame.charge)],dtype=float)
    y=frame.final_single_point_energy_Eh.to_numpy(float); groups=frame.canonical_smiles.fillna(frame.record_id).to_numpy(); predictions=np.full(len(frame),np.nan); splits=min(5,len(set(groups)))
    if splits<2: return pd.Series(predictions,index=frame.index)
    for train,test in GroupKFold(splits).split(X,y,groups): predictions[test]=Ridge(alpha=1.0).fit(X[train],y[train]).predict(X[test])
    return pd.Series(y-predictions,index=frame.index)


def reversible_inclusion(frame: pd.DataFrame, decisions: pd.DataFrame | None = None) -> pd.DataFrame:
    output=frame.copy(); output["include_original_published"]=True; output["include_passed_automated"]=output.qc_status.eq("passed_automated_checks"); output["include_verified_strict"]=output["include_passed_automated"]; output["reviewed_by"]=""; output["reviewed_at"]=""
    if decisions is not None and len(decisions):
        approved=decisions.drop_duplicates("record_key",keep="last").set_index("record_key")
        for idx,key in output.record_key.items():
            action=approved.loc[key,"review_decision"] if key in approved.index else None
            if action in {"include","quarantine","recalculate","exclude"}:
                output.loc[idx,"include_verified_strict"]=action=="include"; output.loc[idx,"reviewed_by"]=approved.loc[key].get("reviewed_by",""); output.loc[idx,"reviewed_at"]=approved.loc[key].get("reviewed_at","")
    return output
