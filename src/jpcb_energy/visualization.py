"""Configurable, graph-preserving 2D molecular rendering."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from io import BytesIO
from math import cos, radians, sin

from PIL import Image
from rdkit import Chem
from rdkit.Chem import Descriptors, rdDepictor, rdMolDescriptors
from rdkit.Chem.Draw import rdMolDraw2D


@dataclass(frozen=True)
class DrawSettings:
    style: str = "heteroatom"
    atom_indices: bool = False
    atom_maps: bool = False
    show_hydrogens: bool = False
    stereo: bool = True
    highlight_charges: bool = True
    smarts: str = ""
    selected_atoms: tuple[int, ...] = ()
    background: str = "white"
    width: int = 720
    height: int = 460
    line_width: float = 2.0
    font_scale: float = 1.0
    rotation: float = 0.0
    padding: float = 0.08


def _mol(smiles: str, settings: DrawSettings) -> Chem.Mol:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    mol = Chem.AddHs(mol) if settings.show_hydrogens else Chem.RemoveHs(mol)
    rdDepictor.Compute2DCoords(mol, canonOrient=True)
    if settings.rotation:
        conf = mol.GetConformer(); angle = radians(settings.rotation)
        for idx in range(mol.GetNumAtoms()):
            point = conf.GetAtomPosition(idx)
            conf.SetAtomPosition(idx, (point.x * cos(angle) - point.y * sin(angle), point.x * sin(angle) + point.y * cos(angle), 0.0))
    if settings.atom_maps:
        for atom in mol.GetAtoms():
            atom.SetAtomMapNum(atom.GetIdx() + 1)
    return mol


def molecule_properties(smiles: str) -> dict:
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        raise ValueError("Invalid SMILES")
    return {
        "canonical_smiles": Chem.MolToSmiles(mol, canonical=True),
        "isomeric_smiles": Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True),
        "formula": rdMolDescriptors.CalcMolFormula(mol),
        "formal_charge": int(Chem.GetFormalCharge(mol)),
        "atoms_without_H": int(mol.GetNumAtoms()),
        "atoms_with_H": int(Chem.AddHs(mol).GetNumAtoms()),
        "heavy_atoms": int(mol.GetNumHeavyAtoms()),
        "exact_mass_Da": float(Descriptors.ExactMolWt(mol)),
    }


def _highlights(mol: Chem.Mol, settings: DrawSettings) -> tuple[list[int], dict[int, tuple[float, float, float]]]:
    atoms = set(settings.selected_atoms)
    if settings.highlight_charges:
        atoms.update(atom.GetIdx() for atom in mol.GetAtoms() if atom.GetFormalCharge())
    if settings.smarts.strip():
        query = Chem.MolFromSmarts(settings.smarts.strip())
        if query is None:
            raise ValueError("Invalid SMARTS pattern")
        for match in mol.GetSubstructMatches(query):
            atoms.update(match)
    colors = {}
    for idx in atoms:
        charge = mol.GetAtomWithIdx(idx).GetFormalCharge()
        colors[idx] = (0.95, 0.36, 0.31) if charge < 0 else (0.0, 0.65, 0.8) if charge > 0 else (1.0, 0.64, 0.2)
    return sorted(atoms), colors


def _options(drawer, settings: DrawSettings, scale: int = 1):
    options = drawer.drawOptions(); options.addAtomIndices = settings.atom_indices
    options.bondLineWidth = settings.line_width * scale; options.baseFontSize = 0.6 * settings.font_scale; options.padding = settings.padding
    options.useBWAtomPalette = settings.style in {"skeleton", "monochrome"}; options.singleColourWedgeBonds = settings.style == "monochrome"
    options.clearBackground = settings.background != "transparent"
    options.setBackgroundColour((1, 1, 1, 1) if settings.background == "white" else (0.04, 0.09, 0.16, 1) if settings.background == "dark" else (1, 1, 1, 0))


def molecule_svg(smiles: str, settings: DrawSettings | bool = DrawSettings(), highlight_charges: bool | None = None, size: tuple[int, int] | None = None, atom_indices: bool | None = None) -> str:
    if atom_indices is not None:
        settings = atom_indices
    if isinstance(settings, bool):
        dimensions = size or (650, 420)
        settings = DrawSettings(atom_indices=settings, highlight_charges=True if highlight_charges is None else highlight_charges, width=dimensions[0], height=dimensions[1])
    mol = _mol(smiles, settings); drawer = rdMolDraw2D.MolDraw2DSVG(settings.width, settings.height); _options(drawer, settings)
    atoms, colors = _highlights(mol, settings); mol = rdMolDraw2D.PrepareMolForDrawing(mol, wedgeBonds=settings.stereo)
    drawer.DrawMolecule(mol, highlightAtoms=atoms, highlightAtomColors=colors)
    drawer.FinishDrawing(); return drawer.GetDrawingText()


def molecule_png_bytes(smiles: str, size: tuple[int, int] = (650, 420), settings: DrawSettings | None = None, scale: int = 1) -> bytes:
    settings = settings or DrawSettings(width=size[0], height=size[1])
    settings = DrawSettings(**{**asdict(settings), "width": int(settings.width * scale), "height": int(settings.height * scale)})
    mol = _mol(smiles, settings); drawer = rdMolDraw2D.MolDraw2DCairo(settings.width, settings.height); _options(drawer, settings, scale)
    atoms, colors = _highlights(mol, settings); mol = rdMolDraw2D.PrepareMolForDrawing(mol, wedgeBonds=settings.stereo)
    drawer.DrawMolecule(mol, highlightAtoms=atoms, highlightAtomColors=colors)
    drawer.FinishDrawing(); return drawer.GetDrawingText()


def molecule_image(smiles: str, size: tuple[int, int] = (500, 350)) -> Image.Image:
    return Image.open(BytesIO(molecule_png_bytes(smiles, size=size)))
