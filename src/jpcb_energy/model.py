"""Model construction, persistence, and metadata validation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import ConstantKernel, RBF, WhiteKernel
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from .descriptors import FEATURES


def build_pipeline(random_state: int = 42) -> Pipeline:
    kernel = (
        ConstantKernel(1.0, (1e-3, 1e3))
        * RBF(length_scale=1.0, length_scale_bounds=(1e-2, 1e2))
        + WhiteKernel(noise_level=1e-3, noise_level_bounds=(1e-6, 1e1))
    )
    return Pipeline(
        [
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "model",
                GaussianProcessRegressor(
                    kernel=kernel,
                    alpha=1e-6,
                    normalize_y=True,
                    random_state=random_state,
                ),
            ),
        ]
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_model(model_dir: str | Path) -> tuple[Pipeline, dict]:
    root = Path(model_dir)
    model_path = root / "gpr_model.joblib"
    metadata_path = root / "model_metadata.json"
    if not model_path.exists() or not metadata_path.exists():
        raise FileNotFoundError(f"Model files are missing from {root}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if metadata.get("feature_order") != FEATURES:
        raise ValueError("Model feature order does not match the software feature contract")
    expected = metadata.get("model_sha256")
    if expected and sha256(model_path) != expected:
        raise ValueError("Model SHA-256 validation failed")
    model = joblib.load(model_path)
    if not isinstance(model, Pipeline) or list(model.named_steps) != ["imputer", "scaler", "model"]:
        raise ValueError("The artifact is not the required complete sklearn Pipeline")
    return model, metadata

