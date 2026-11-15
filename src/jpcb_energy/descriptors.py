"""Molecular standardization and the eight published Mordred descriptors."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

import numpy as np
from mordred import Calculator, descriptors
from rdkit import Chem
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
    return Calculator(descriptors, ignore_3D=True)


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

