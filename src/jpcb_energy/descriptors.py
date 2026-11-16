"""Molecular standardization and the eight published Mordred descriptors."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
from mordred import Calculator, descriptors
from rdkit import Chem
from rdkit.Chem import Descriptors as RDDescriptors
from rdkit.Chem.MolStandardize import rdMolStandardize

FEATURES = [
    "mordred_ATS0m",
    "mordred_ZMIC2",
    "mordred_ATSC0p",
    "mordred_ATS2s",
    "mordred_VR2_D",
    "mordred_AETA_eta_R",
    "mordred_ETA_eta_F",
    "mordred_ATSC0dv",
]


class MoleculeError(ValueError):
    """Raised when a molecule cannot be parsed or featurized."""


def standardize_smiles(smiles: str) -> tuple[str, Chem.Mol]:
    if not isinstance(smiles, str) or not smiles.strip():
        raise MoleculeError("SMILES is empty")
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        raise MoleculeError("RDKit could not parse the SMILES")
    try:
        mol = rdMolStandardize.Cleanup(mol)
        Chem.SanitizeMol(mol)
    except Exception as exc:
        raise MoleculeError(f"RDKit standardization failed: {exc}") from exc
    return Chem.MolToSmiles(mol, canonical=True, isomericSmiles=True), mol


@lru_cache(maxsize=1)
def _calculator() -> Calculator:
    all_descriptors = Calculator(descriptors, ignore_3D=True)
    wanted = {name.removeprefix("mordred_") for name in FEATURES}
    selected = [descriptor for descriptor in all_descriptors.descriptors if str(descriptor) in wanted]
    if {str(descriptor) for descriptor in selected} != wanted:
        raise RuntimeError("The installed Mordred version does not provide the exact eight-feature contract")
    return Calculator(selected, ignore_3D=True)


def calculate_descriptors(smiles: str) -> tuple[str, dict[str, float]]:
    canonical, mol = standardize_smiles(smiles)
    mol_h = Chem.AddHs(mol)
    raw: dict[str, Any] = _calculator()(mol_h).asdict()
    result: dict[str, float] = {}
    for feature in FEATURES:
        key = feature.removeprefix("mordred_")
        try:
            value = float(raw[key])
        except Exception as exc:
            raise MoleculeError(f"Descriptor {key} is unavailable: {raw.get(key)!r}") from exc
        result[feature] = value if np.isfinite(value) else np.nan
    return canonical, result


def calculate_rdkit_panel(smiles: str) -> tuple[str, dict[str, float]]:
    """Return a compact, interpretable exploratory descriptor panel."""
    canonical, mol = standardize_smiles(smiles)
    panel = {
        "MolWt_g_mol": RDDescriptors.MolWt(mol),
        "ExactMolWt_g_mol": RDDescriptors.ExactMolWt(mol),
        "HeavyAtomCount": float(RDDescriptors.HeavyAtomCount(mol)),
        "TotalAtomCount_with_H": float(Chem.AddHs(mol).GetNumAtoms()),
        "FormalCharge": float(Chem.GetFormalCharge(mol)),
        "HBD": float(RDDescriptors.NumHDonors(mol)),
        "HBA": float(RDDescriptors.NumHAcceptors(mol)),
        "RotatableBonds": float(RDDescriptors.NumRotatableBonds(mol)),
        "RingCount": float(RDDescriptors.RingCount(mol)),
        "TPSA_A2": RDDescriptors.TPSA(mol),
        "MolLogP": RDDescriptors.MolLogP(mol),
        "FractionCSP3": RDDescriptors.FractionCSP3(mol),
    }
    return canonical, panel


def molecular_warnings(smiles: str) -> list[str]:
    """Return transparent chemistry-domain warnings without altering structure."""
    _, mol = standardize_smiles(smiles)
    warnings: list[str] = []
    supported = {1, 5, 6, 7, 8, 9, 14, 15, 16, 17, 32, 33, 34, 35, 50, 53, 82}
    unsupported = sorted({atom.GetSymbol() for atom in mol.GetAtoms() if atom.GetAtomicNum() not in supported})
    if unsupported:
        warnings.append("unsupported_elements:" + ",".join(unsupported))
    if any(atom.GetNumRadicalElectrons() for atom in mol.GetAtoms()):
        warnings.append("radical_structure")
    charges = [atom.GetFormalCharge() for atom in mol.GetAtoms()]
    if any(c > 0 for c in charges) and any(c < 0 for c in charges):
        warnings.append("zwitterionic_or_charge_separated_structure")
    if len(Chem.GetMolFrags(mol)) > 1:
        warnings.append("multiple_fragments_or_explicit_counterion")
    if mol.GetNumHeavyAtoms() > 80:
        warnings.append("large_structure_outside_intended_monomer_scale")
    return warnings

