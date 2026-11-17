#!/usr/bin/env python
"""Render key pages with Streamlit's test runtime before launching the server."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from streamlit.testing.v1 import AppTest


ROOT=Path(__file__).resolve().parents[1]
APP=ROOT/"src"/"jpcb_energy"/"app.py"


def render(page: str) -> dict:
    test=AppTest.from_file(str(APP),default_timeout=60)
    test.query_params["page"]=page
    test.run()
    exceptions=[str(item.value) for item in test.exception]
    return {"page":page,"exceptions":exceptions,"passed":not exceptions}


def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument("--startup",action="store_true"); arguments=parser.parse_args()
    pages=["Predict"] if arguments.startup else ["Predict","Molecular Explorer","Data Cleaning & Outlier Removal","About & Citation"]
    results=[render(page) for page in pages]
    report={"application":str(APP),"pages":results,"passed":all(result["passed"] for result in results)}
    print(json.dumps(report,indent=2))
    return 0 if report["passed"] else 1


if __name__=="__main__": raise SystemExit(main())
