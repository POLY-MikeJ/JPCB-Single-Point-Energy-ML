"""Immutable official model registry."""

from __future__ import annotations

import json
from pathlib import Path

import joblib

from .model import load_model, sha256


def discover_models(project_root: str | Path) -> dict[str, dict]:
    root = Path(project_root)
    models = {}
    legacy_model, legacy_meta = load_model(root / "models")
    models["v1.0.0-vacuum-reference"] = {"pipeline": legacy_model, "metadata": legacy_meta, "path": root / "models" / "gpr_model.joblib", "immutable": True}
    enhanced = root / "models" / "v1.1.0"
    if enhanced.exists():
        for metadata_path in enhanced.glob("*/model_metadata.json"):
            meta = json.loads(metadata_path.read_text(encoding="utf-8"))
            artifact = metadata_path.parent / "model.joblib"
            if sha256(artifact) != meta["model_sha256"]:
                raise ValueError(f"Model checksum failed: {artifact}")
            bundle = joblib.load(artifact)
            models[meta["model_id"]] = {"pipeline": bundle["pipeline"], "domain_profile": bundle["domain_profile"], "metadata": meta, "path": artifact, "immutable": True}
    return models
