#!/usr/bin/env python
import argparse
import json
from pathlib import Path
import pandas as pd
from jpcb_energy.orca_parser import parse_orca

parser = argparse.ArgumentParser(description="Parse ORCA .out files")
parser.add_argument("input", type=Path)
parser.add_argument("output", type=Path)
args = parser.parse_args()
files = [args.input] if args.input.is_file() else sorted(args.input.rglob("*.out"))
rows = []
for path in files:
    row = parse_orca(path)
    row["frequencies_cm-1"] = json.dumps(row["frequencies_cm-1"])
    rows.append(row)
pd.DataFrame(rows).to_csv(args.output, index=False)
print(f"Parsed {len(rows)} files -> {args.output.resolve()}")

