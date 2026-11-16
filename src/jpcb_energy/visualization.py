"""Molecule drawing helpers with reproducible export."""

from io import BytesIO

from rdkit import Chem
from rdkit.Chem import Draw
from rdkit.Chem.Draw import rdMolDraw2D


def molecule_image(smiles: str, size: tuple[int, int] = (500, 350)):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    return Draw.MolToImage(mol, size=size)


def molecule_svg(smiles: str, atom_indices: bool = False, highlight_charges: bool = True, size: tuple[int, int] = (650, 420)) -> str:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    drawer = rdMolDraw2D.MolDraw2DSVG(*size)
    drawer.drawOptions().addAtomIndices = atom_indices
    highlighted = [atom.GetIdx() for atom in mol.GetAtoms() if atom.GetFormalCharge()] if highlight_charges else []
    colors = {idx: (0.0, 0.65, 0.80) if mol.GetAtomWithIdx(idx).GetFormalCharge() > 0 else (0.85, 0.25, 0.30) for idx in highlighted}
    rdMolDraw2D.PrepareAndDrawMolecule(drawer, mol, highlightAtoms=highlighted, highlightAtomColors=colors)
    drawer.FinishDrawing()
    return drawer.GetDrawingText()


def molecule_png_bytes(smiles: str, size: tuple[int, int] = (650, 420)) -> bytes:
    image = molecule_image(smiles, size=size)
    buffer = BytesIO(); image.save(buffer, format="PNG"); return buffer.getvalue()

