#!/usr/bin/env python
import argparse
from pathlib import Path
import pandas as pd
from jpcb_energy.prediction import predict_batch

parser = argparse.ArgumentParser(description="Batch-predict a CSV containing smiles")
parser.add_argument("input", type=Path)
parser.add_argument("output", type=Path)
parser.add_argument("--model-dir", type=Path, default=Path(__file__).resolve().parents[1] / "models")
args = parser.parse_args()
predict_batch(pd.read_csv(args.input), args.model_dir).to_csv(args.output, index=False)
print(args.output.resolve())

