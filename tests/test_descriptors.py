import pytest
from jpcb_energy.descriptors import FEATURES, MoleculeError, calculate_descriptors


def test_valid_smiles_has_ordered_features():
    canonical, values = calculate_descriptors("C=CC(=O)N")
    assert canonical
    assert list(values) == FEATURES


def test_invalid_smiles():
    with pytest.raises(MoleculeError):
        calculate_descriptors("not-a-smiles")

