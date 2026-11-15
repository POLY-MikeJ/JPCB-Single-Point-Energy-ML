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
    header = "\n".join(text.splitlines()[:250]).lower()
    task = "frequency" if " freq" in header or freqs else "optimization" if " opt" in header else "single_point"
    solvents = re.findall(r"cpcm\(([^)]+)\)", header, flags=re.I)
    digest = hashlib.sha256(raw).hexdigest()
    return {
        "file_name": source.name,
        "source_path": str(source.resolve()),
        "sha256": digest,
        "task_type": task,
        "solvent": solvents[-1].lower() if solvents else "vacuum",
        "normal_termination": "ORCA TERMINATED NORMALLY" in text,
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

