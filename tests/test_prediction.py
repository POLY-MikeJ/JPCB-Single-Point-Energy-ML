from pathlib import Path
import pandas as pd
import pytest
from jpcb_energy.prediction import predict_batch, predict_one

ROOT = Path(__file__).resolve().parents[1]


def test_model_load_and_single_prediction():
    result = predict_one("C=CC(=O)N", ROOT / "models")
    assert result["unit"] == "Eh"
    assert result["prediction"] < 0


def test_batch_is_fault_tolerant_and_marks_duplicates():
    frame = pd.DataFrame({"id": [1, 2, 3], "smiles": ["C=CC(=O)N", "bad", "C=CC(=O)N"]})
    result = predict_batch(frame, ROOT / "models")
    assert list(result.status) == ["ok", "error", "ok"]
    assert bool(result.loc[2, "duplicate_input"])
    assert result.loc[0, "predicted_E_sp_Eh"] == result.loc[2, "predicted_E_sp_Eh"]


def test_batch_requires_smiles():
    with pytest.raises(ValueError):
        predict_batch(pd.DataFrame({"name": ["x"]}), ROOT / "models")

