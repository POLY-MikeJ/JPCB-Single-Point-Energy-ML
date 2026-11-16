"""Reproducible 3D conformer generation, comparison, rendering and export."""

from __future__ import annotations

from io import BytesIO

from rdkit import Chem
from rdkit.Chem import AllChem, rdMolAlign

from .descriptors import standardize_smiles


def generate_conformers(smiles: str, seed: int = 42, count: int = 1, force_field: str = "MMFF94") -> tuple[list[Chem.Mol], list[dict]]:
    canonical, base = standardize_smiles(smiles); base = Chem.AddHs(Chem.Mol(base))
    params = AllChem.ETKDGv3(); params.randomSeed = int(seed); params.pruneRmsThresh = 0.25; params.numThreads = 1
    ids = list(AllChem.EmbedMultipleConfs(base, numConfs=int(count), params=params))
    if not ids: raise ValueError("ETKDG conformer generation failed")
    molecules, metadata = [], []
    for rank, conformer_id in enumerate(ids):
        mol = Chem.Mol(base); conf = Chem.Conformer(base.GetConformer(conformer_id)); mol.RemoveAllConformers(); mol.AddConformer(conf, assignId=True)
        method, energy, converged = "ETKDGv3 only", None, None
        try:
            if force_field in {"MMFF94", "MMFF94s"} and AllChem.MMFFHasAllMoleculeParams(mol):
                properties = AllChem.MMFFGetMoleculeProperties(mol, mmffVariant=force_field); field = AllChem.MMFFGetMoleculeForceField(mol, properties)
                converged = field.Minimize(maxIts=500) == 0; energy = float(field.CalcEnergy()); method = f"ETKDGv3 + {force_field}"
            elif force_field == "UFF" or not AllChem.MMFFHasAllMoleculeParams(mol):
                field = AllChem.UFFGetMoleculeForceField(mol); converged = field.Minimize(maxIts=500) == 0; energy = float(field.CalcEnergy()); method = "ETKDGv3 + UFF"
        except Exception: method = "ETKDGv3; force-field optimization unavailable"
        molecules.append(mol); metadata.append({"conformer":rank+1,"canonical_smiles":canonical,"seed":seed,"force_field":force_field,"method":method,"force_field_energy":energy,"converged":converged,"geometry_source":"RDKit force-field optimized" if energy is not None else "RDKit ETKDG","geometry_role":"illustrative local conformer; not an ORCA-optimized geometry and not used by the 2D descriptor model"})
    order = sorted(range(len(molecules)), key=lambda idx: float("inf") if metadata[idx]["force_field_energy"] is None else metadata[idx]["force_field_energy"])
    return [molecules[idx] for idx in order], [metadata[idx] for idx in order]


def generate_conformer(smiles: str, seed: int = 42) -> tuple[Chem.Mol, dict]:
    molecules, metadata = generate_conformers(smiles, seed, 1, "MMFF94"); return molecules[0], metadata[0]


def conformer_rmsd(reference: Chem.Mol, probe: Chem.Mol) -> float:
    if [a.GetAtomicNum() for a in reference.GetAtoms()] != [a.GetAtomicNum() for a in probe.GetAtoms()]: raise ValueError("RMSD requires identical atom ordering and elements")
    return float(rdMolAlign.GetBestRMS(probe, reference))


def conformer_sdf(mol: Chem.Mol, title: str = "ZHU MolEnergy conformer") -> str:
    result = Chem.Mol(mol); result.SetProp("_Name", title); return Chem.MolToMolBlock(result) + "\n$$$$\n"


def conformer_xyz(mol: Chem.Mol, comment: str = "RDKit illustrative conformer") -> str:
    conf = mol.GetConformer(); lines = [str(mol.GetNumAtoms()), comment]
    for atom in mol.GetAtoms():
        point = conf.GetAtomPosition(atom.GetIdx()); lines.append(f"{atom.GetSymbol():2s} {point.x: .8f} {point.y: .8f} {point.z: .8f}")
    return "\n".join(lines) + "\n"


def plotly_figure(mol: Chem.Mol, style: str = "ball-and-stick", color_scheme: str = "CPK", background: str = "light", show_hydrogens: bool = True, labels: str = "none", atom_scale: float = 1.0, bond_width: float = 5.0, auto_spin: bool = False):
    import plotly.graph_objects as go
    hidden = {idx for idx, atom in enumerate(mol.GetAtoms()) if atom.GetAtomicNum() == 1 and not show_hydrogens}; conf = mol.GetConformer()
    cpk = {1:"#E8EEF7",6:"#334155",7:"#2563EB",8:"#EF4444",9:"#14B8A6",15:"#F59E0B",16:"#EAB308",17:"#22C55E",35:"#A16207",53:"#7C3AED"}; traces = []
    for bond in mol.GetBonds():
        first, second = bond.GetBeginAtomIdx(), bond.GetEndAtomIdx()
        if first in hidden or second in hidden: continue
        a,b=conf.GetAtomPosition(first),conf.GetAtomPosition(second); traces.append(go.Scatter3d(x=[a.x,b.x],y=[a.y,b.y],z=[a.z,b.z],mode="lines",line={"color":"#94A3B8","width":2 if style=="wireframe" else bond_width},hoverinfo="skip",showlegend=False))
    if style != "stick":
        xs=[]; ys=[]; zs=[]; hover=[]; colors=[]; sizes=[]; labels_text=[]
        for idx,atom in enumerate(mol.GetAtoms()):
            if idx in hidden: continue
            point=conf.GetAtomPosition(idx); xs.append(point.x); ys.append(point.y); zs.append(point.z); hover.append(f"{atom.GetSymbol()} {idx} · formal charge {atom.GetFormalCharge()}"); colors.append("#06B6D4" if color_scheme=="monochrome" else cpk.get(atom.GetAtomicNum(),"#64748B")); sizes.append((15 if style=="sphere" else 8)*atom_scale); labels_text.append(str(idx) if labels=="index" else atom.GetSymbol() if labels=="element" else "")
        traces.append(go.Scatter3d(x=xs,y=ys,z=zs,mode="markers+text" if labels!="none" else "markers",marker={"size":sizes,"color":colors,"line":{"width":1,"color":"#0F172A"}},text=labels_text,textposition="top center",hovertext=hover,hoverinfo="text",showlegend=False))
    background_color = "rgba(0,0,0,0)" if background=="transparent" else "#07111F" if background=="dark" else "#F8FAFC"
    figure=go.Figure(traces); figure.update_layout(margin={"l":8,"r":8,"t":8,"b":8},paper_bgcolor=background_color,scene={"bgcolor":background_color,"xaxis":{"visible":False},"yaxis":{"visible":False},"zaxis":{"visible":False},"aspectmode":"data","camera":{"center":{"x":0,"y":0,"z":0},"eye":{"x":1.55,"y":1.55,"z":1.15},"projection":{"type":"perspective"}}},uirevision="zhu-molenergy-3d",meta={"auto_spin_requested":bool(auto_spin)})
    return figure


def conformer_png_bytes(mol: Chem.Mol, width: int = 1200, height: int = 800) -> bytes:
    import matplotlib.pyplot as plt
    conf=mol.GetConformer(); figure=plt.figure(figsize=(width/150,height/150),dpi=150); axis=figure.add_subplot(111,projection="3d"); colors={1:"#E8EEF7",6:"#334155",7:"#2563EB",8:"#EF4444",16:"#EAB308"}
    for bond in mol.GetBonds():
        a,b=conf.GetAtomPosition(bond.GetBeginAtomIdx()),conf.GetAtomPosition(bond.GetEndAtomIdx()); axis.plot([a.x,b.x],[a.y,b.y],[a.z,b.z],color="#94A3B8",linewidth=2)
    for atom in mol.GetAtoms():
        point=conf.GetAtomPosition(atom.GetIdx()); axis.scatter(point.x,point.y,point.z,s=90,color=colors.get(atom.GetAtomicNum(),"#64748B"),edgecolor="#0F172A")
    axis.set_axis_off(); axis.set_box_aspect((1,1,1)); buffer=BytesIO(); figure.savefig(buffer,format="png",transparent=True,bbox_inches="tight"); plt.close(figure); return buffer.getvalue()
