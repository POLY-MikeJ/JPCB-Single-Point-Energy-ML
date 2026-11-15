#!/usr/bin/env python
import argparse
import json
from pathlib import Path
from jpcb_energy.prediction import predict_one

parser = argparse.ArgumentParser(description="Predict E_sp for one SMILES")
parser.add_argument("smiles")
parser.add_argument("--model-dir", type=Path, default=Path(__file__).resolve().parents[1] / "models")
args = parser.parse_args()
print(json.dumps(predict_one(args.smiles, args.model_dir), indent=2))

