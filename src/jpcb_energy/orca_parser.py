"""Task-aware ORCA 6 output parser."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

ENERGY = re.compile(r"FINAL SINGLE POINT ENERGY\s+(-?\d+\.\d+)")
ZPE = re.compile(r"Zero point energy\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh", re.I)
THERMAL = re.compile(r"Total thermal energy\s+(?:\.\.\.\s+)?(-?\d+\.\d+)\s+Eh", re.I)
ENTHALPY = re.compile(r"Total Enthalpy\s+(?:\.\.\.\s+)?(-?\d+\.\d+)\s+Eh", re.I)
GIBBS = re.compile(r"Final Gibbs free energy\s+\.\.\.\s+(-?\d+\.\d+)\s+Eh", re.I)
FREQUENCY = re.compile(r"^\s*\d+:\s+(-?\d+\.\d+)\s+cm\*\*-1", re.M)
EPSILON = re.compile(r"^\s*Epsilon\s+\.\.\.\s+([0-9]+(?:\.[0-9]+)?)\s*$", re.M | re.I)
XYZ_HEADER = re.compile(r"^\s*(?:\|\s*\d+>\s*)?\*\s*xyz(?:file)?\s+(-?\d+)\s+(\d+)", re.M | re.I)
INPUT_LINE = re.compile(r"^\s*(?:\|\s*\d+>\s*)?!\s+(.+)$", re.M)


def _last(pattern: re.Pattern, text: str) -> float | None:
    values = pattern.findall(text)
    return float(values[-1]) if values else None


def parse_orca(path: str | Path) -> dict:
    source = Path(path)
    raw = source.read_bytes()
    encoding = "utf-16" if raw.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8"
    text = raw.decode(encoding, errors="replace")
    energies = [float(x) for x in ENERGY.findall(text)]
    freqs = [float(x) for x in FREQUENCY.findall(text)]
    lower = text.lower()
    input_lines = INPUT_LINE.findall(text)
    keywords = input_lines[0].strip() if input_lines else ""
    keyword_lower = keywords.lower()
    task = "frequency" if " freq" in " " + keyword_lower or freqs else "optimization" if " opt" in " " + keyword_lower else "single_point"
    solvents = re.findall(r"cpcm\(([^)]+)\)", keywords, flags=re.I)
    epsilon = EPSILON.findall(text)
    xyz = XYZ_HEADER.findall(text)
    tokens = keywords.split()
    method = next((x for x in tokens if x.upper() in {"B3LYP", "PBE0", "BP86", "M06-2X", "HF"}), None)
    basis = next((x for x in tokens if any(mark in x.upper() for mark in ["6-311", "DEF2", "CC-PV", "STO-"])), None)
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "file_name": source.name,
        "source_path": str(source.resolve()),
        "sha256": digest,
        "task_type": task,
        "solvent": solvents[-1].lower() if solvents else "vacuum",
        "dielectric_constant": float(epsilon[-1]) if epsilon else (1.0 if not solvents else None),
        "method": method,
        "basis_set": basis,
        "charge": int(xyz[-1][0]) if xyz else None,
        "multiplicity": int(xyz[-1][1]) if xyz else None,
        "keywords": keywords,
        "normal_termination": "ORCA TERMINATED NORMALLY" in text,
        "scf_converged": "SCF CONVERGED" in text.upper() or "ORCA TERMINATED NORMALLY" in text,
        "optimization_converged": "THE OPTIMIZATION HAS CONVERGED" in text.upper() if task == "optimization" else None,
        "final_single_point_energy_Eh": energies[-1] if energies else None,
        "energy_occurrence_count": len(energies),
        "zero_point_energy_Eh": _last(ZPE, text),
        "total_thermal_energy_Eh": _last(THERMAL, text),
        "enthalpy_Eh": _last(ENTHALPY, text),
        "gibbs_free_energy_Eh": _last(GIBBS, text),
        "frequencies_cm-1": freqs,
        "imaginary_frequency_count": sum(f < -1.0 for f in freqs),
        "minimum_frequency_cm-1": min(freqs) if freqs else None,
        "paper_model_target_Eh": energies[-1] if task == "frequency" and energies else None,
    }


def index_orca_folder(folder: str | Path) -> list[dict]:
    """Recursively parse outputs without modifying the source directory."""
    return [parse_orca(path) for path in sorted(Path(folder).rglob("*.out"))]

