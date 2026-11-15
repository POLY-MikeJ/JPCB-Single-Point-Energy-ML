"""Molecule drawing helpers."""

from rdkit import Chem
from rdkit.Chem import Draw


def molecule_image(smiles: str, size: tuple[int, int] = (500, 350)):
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    return Draw.MolToImage(mol, size=size)

