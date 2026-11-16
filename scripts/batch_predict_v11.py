#!/usr/bin/env python
import argparse, json
from pathlib import Path
import pandas as pd
from jpcb_energy.registry import discover_models
from jpcb_energy.workbench import batch_predict

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description="High-throughput CSV energy screening")
parser.add_argument("input", type=Path); parser.add_argument("output", type=Path); parser.add_argument("--model-id", default="v1.1.0-gpr-water"); parser.add_argument("--chunk-size", type=int, default=500)
args = parser.parse_args(); models = discover_models(root)
if args.model_id not in models: raise SystemExit(f"Unknown model ID: {args.model_id}")
result, summary = batch_predict(pd.read_csv(args.input), models[args.model_id], args.chunk_size); result.to_csv(args.output, index=False); print(json.dumps(summary, indent=2)); print(args.output.resolve())
