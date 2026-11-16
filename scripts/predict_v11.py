#!/usr/bin/env python
import argparse, json
from pathlib import Path
from jpcb_energy.registry import discover_models
from jpcb_energy.workbench import predict_with_bundle

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="Predict environment-specific electronic energy")
parser.add_argument("smiles"); parser.add_argument("--model-id", default="v1.1.0-gpr-water")
args = parser.parse_args(); models = discover_models(root)
if args.model_id not in models: raise SystemExit(f"Unknown model ID. Available: {', '.join(models)}")
result = predict_with_bundle(args.smiles, models[args.model_id]); result["model_id"] = args.model_id; result["target_definition"] = models[args.model_id]["metadata"]["target_definition"]
print(json.dumps(result, indent=2))
