"""Reproducible illustrative 3D conformer generation and export."""

from __future__ import annotations

from io import StringIO

from rdkit import Chem
from rdkit.Chem import AllChem

from .descriptors import standardize_smiles


def generate_conformer(smiles: str, seed: int = 42) -> tuple[Chem.Mol, dict]:
    canonical, mol = standardize_smiles(smiles)
    mol = Chem.AddHs(Chem.Mol(mol))
    params = AllChem.ETKDGv3()
    params.randomSeed = int(seed)
    if AllChem.EmbedMolecule(mol, params) != 0:
        raise ValueError("ETKDG conformer generation failed")
    method = "ETKDGv3 only"
    try:
        if AllChem.MMFFHasAllMoleculeParams(mol):
            AllChem.MMFFOptimizeMolecule(mol, mmffVariant="MMFF94", maxIters=500)
            method = "ETKDGv3 + MMFF94"
        else:
            AllChem.UFFOptimizeMolecule(mol, maxIters=500)
            method = "ETKDGv3 + UFF fallback"
    except Exception:
        method = "ETKDGv3; force-field optimization unavailable"
    return mol, {"canonical_smiles": canonical, "seed": seed, "method": method, "geometry_role": "illustrative RDKit-generated conformer; not an ORCA-optimized geometry and not used by the 2D descriptor model"}


def conformer_sdf(mol: Chem.Mol) -> str:
    return Chem.MolToMolBlock(mol) + "\n$$$$\n"


def conformer_xyz(mol: Chem.Mol) -> str:
    conf = mol.GetConformer()
    lines = [str(mol.GetNumAtoms()), "RDKit illustrative conformer"]
    for atom in mol.GetAtoms():
        p = conf.GetAtomPosition(atom.GetIdx())
        lines.append(f"{atom.GetSymbol():2s} {p.x: .8f} {p.y: .8f} {p.z: .8f}")
    return "\n".join(lines) + "\n"


def plotly_figure(mol: Chem.Mol):
    import plotly.graph_objects as go

    conf = mol.GetConformer()
    colors = {1: "#E8EEF7", 6: "#34495E", 7: "#2471A3", 8: "#C0392B", 9: "#1ABC9C", 15: "#D4AC0D", 16: "#F4D03F", 17: "#27AE60", 35: "#A04000", 53: "#6C3483"}
    traces = []
    for bond in mol.GetBonds():
        a, b = conf.GetAtomPosition(bond.GetBeginAtomIdx()), conf.GetAtomPosition(bond.GetEndAtomIdx())
        traces.append(go.Scatter3d(x=[a.x, b.x], y=[a.y, b.y], z=[a.z, b.z], mode="lines", line={"color": "#8395A7", "width": 5}, hoverinfo="skip", showlegend=False))
    xs, ys, zs, text, color = [], [], [], [], []
    for atom in mol.GetAtoms():
        p = conf.GetAtomPosition(atom.GetIdx())
        xs.append(p.x); ys.append(p.y); zs.append(p.z)
        text.append(f"{atom.GetSymbol()} {atom.GetIdx()} charge={atom.GetFormalCharge()}")
        color.append(colors.get(atom.GetAtomicNum(), "#7F8C8D"))
    traces.append(go.Scatter3d(x=xs, y=ys, z=zs, mode="markers", marker={"size": 8, "color": color, "line": {"width": 1, "color": "#17202A"}}, text=text, hoverinfo="text", showlegend=False))
    fig = go.Figure(traces)
    fig.update_layout(margin={"l": 0, "r": 0, "t": 20, "b": 0}, paper_bgcolor="#F8FAFD", scene={"xaxis": {"visible": False}, "yaxis": {"visible": False}, "zaxis": {"visible": False}, "aspectmode": "data"})
    return fig
