"""Safe local GFN2-xTB adapter. It never installs or downloads xTB."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from rdkit import Chem
from rdkit.Geometry import Point3D

from .conformer import conformer_sdf, conformer_xyz, generate_conformers


XTB_ENERGY = re.compile(r"TOTAL ENERGY\s+(-?\d+\.\d+)\s+Eh", re.I)
SUPPORTED_ALPB = {"water", "methanol", "ethanol", "acetone", "acetonitrile", "benzene", "chloroform", "dichloromethane", "dmso", "ether", "toluene", "thf"}


@dataclass(frozen=True)
class XTBInstallation:
    available: bool
    executable: str | None
    version: str | None
    message: str


def detect_xtb(explicit_path: str | Path | None = None) -> XTBInstallation:
    candidate = Path(explicit_path).expanduser() if explicit_path else None
    portable_root = Path(__file__).resolve().parents[2] / "local_tools"
    portable = next(portable_root.rglob("xtb.exe"), None) if portable_root.is_dir() else None
    resolved = str(candidate.resolve()) if candidate and candidate.is_file() else shutil.which("xtb") or shutil.which("xtb.exe") or (str(portable.resolve()) if portable else None)
    if not resolved:
        return XTBInstallation(False, None, None, "xTB was not found. Configure an existing native Windows xtb.exe; this application does not install or bundle xTB.")
    try:
        completed = subprocess.run([resolved, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15, shell=False, check=False)
        output = (completed.stdout + "\n" + completed.stderr).strip()
        if completed.returncode != 0:
            return XTBInstallation(False, resolved, None, f"xTB version check failed with exit code {completed.returncode}: {output[-300:]}")
        version = next((line.strip() for line in output.splitlines() if "version" in line.lower()), output.splitlines()[0] if output else "version not reported")
        return XTBInstallation(True, resolved, version, "Verified local xTB executable")
    except (OSError, subprocess.TimeoutExpired) as exc:
        return XTBInstallation(False, resolved, None, f"xTB executable could not be verified: {exc}")


def build_xtb_command(executable: str, input_name: str, charge: int, unpaired_electrons: int, solvent: str | None = None, opt_level: str = "tight") -> list[str]:
    if Path(input_name).name != input_name or not input_name.lower().endswith(".xyz"):
        raise ValueError("xTB input must be a simple local .xyz filename")
    if not (-10 <= int(charge) <= 10 and 0 <= int(unpaired_electrons) <= 10):
        raise ValueError("Charge or number of unpaired electrons is outside the allowed safeguard range")
    command = [str(executable), input_name, "--gfn", "2", "--opt", opt_level, "--chrg", str(int(charge)), "--uhf", str(int(unpaired_electrons))]
    if solvent:
        solvent = solvent.lower().strip()
        if solvent not in SUPPORTED_ALPB:
            raise ValueError(f"Unsupported ALPB solvent: {solvent}")
        command += ["--alpb", solvent]
    return command


def parse_xtb_output(text: str, job_dir: Path) -> dict:
    energies = [float(value) for value in XTB_ENERGY.findall(text)]; optimized = job_dir / "xtbopt.xyz"
    converged = "GEOMETRY OPTIMIZATION CONVERGED" in text.upper() or "optimization converged" in text.lower()
    return {"converged":converged and optimized.is_file(),"initial_energy_Eh":energies[0] if energies else None,"final_energy_Eh":energies[-1] if energies else None,"energy_change_Eh":energies[-1]-energies[0] if len(energies)>=2 else None,"energy_occurrences":len(energies),"optimized_xyz":str(optimized) if optimized.is_file() else None}


def molecule_from_xyz(template: Chem.Mol, xyz_path: str | Path) -> Chem.Mol:
    lines=Path(xyz_path).read_text(encoding="utf-8",errors="replace").splitlines(); count=int(lines[0]); coordinates=lines[2:2+count]
    if count!=template.GetNumAtoms(): raise ValueError("xTB optimized atom count does not match the input template")
    result=Chem.Mol(template); conformer=Chem.Conformer(count)
    for index,line in enumerate(coordinates):
        fields=line.split()
        if len(fields)<4 or fields[0].lower()!=result.GetAtomWithIdx(index).GetSymbol().lower(): raise ValueError("xTB optimized atom ordering/elements do not match the input template")
        conformer.SetAtomPosition(index,Point3D(float(fields[1]),float(fields[2]),float(fields[3])))
    result.RemoveAllConformers(); result.AddConformer(conformer,assignId=True); return result


def run_xtb(smiles: str, executable: str, jobs_root: str | Path, charge: int, unpaired_electrons: int, solvent: str | None = None, timeout_seconds: int = 900, max_atoms: int = 250, seed: int = 42) -> dict:
    installation = detect_xtb(executable)
    if not installation.available: raise RuntimeError(installation.message)
    molecules, conformer_info = generate_conformers(smiles, seed, 1, "MMFF94"); molecule = molecules[0]
    if molecule.GetNumAtoms() > max_atoms: raise ValueError(f"Molecule has {molecule.GetNumAtoms()} atoms including H; limit is {max_atoms}")
    job_id=f"xtb-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"; job_dir=Path(jobs_root).resolve()/job_id; job_dir.mkdir(parents=True,exist_ok=False)
    input_path=job_dir/"input.xyz"; input_path.write_text(conformer_xyz(molecule,"RDKit input geometry for GFN2-xTB"),encoding="utf-8"); (job_dir/"input.sdf").write_text(conformer_sdf(molecule,"RDKit input geometry"),encoding="utf-8")
    command=build_xtb_command(installation.executable or executable,input_path.name,charge,unpaired_electrons,solvent); started=time.perf_counter()
    metadata={"job_id":job_id,"status":"running","method":"GFN2-xTB","solvation_model":f"ALPB({solvent})" if solvent else "gas phase","charge":charge,"unpaired_electrons":unpaired_electrons,"command_arguments":command[1:],"executable":installation.executable,"input_geometry":conformer_info[0],"timeout_seconds":timeout_seconds}
    (job_dir/"job.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    try:
        completed=subprocess.run(command,cwd=job_dir,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout_seconds,shell=False,check=False,env={**os.environ,"OMP_NUM_THREADS":"1"})
        log=completed.stdout+"\n"+completed.stderr; (job_dir/"xtb.log").write_text(log,encoding="utf-8",errors="replace"); parsed=parse_xtb_output(log,job_dir)
        if parsed["converged"]:
            optimized_molecule=molecule_from_xyz(molecule,parsed["optimized_xyz"]); optimized_sdf=job_dir/"optimized.sdf"; optimized_sdf.write_text(conformer_sdf(optimized_molecule,"GFN2-xTB optimized geometry"),encoding="utf-8"); parsed["optimized_sdf"]=str(optimized_sdf)
        metadata.update(parsed); metadata.update({"status":"completed" if completed.returncode==0 and parsed["converged"] else "failed","return_code":completed.returncode,"runtime_seconds":time.perf_counter()-started})
    except subprocess.TimeoutExpired as exc: metadata.update({"status":"timeout","runtime_seconds":time.perf_counter()-started,"error":str(exc)})
    (job_dir/"job.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8"); return metadata


def rdkit_optimize(smiles: str, seed: int = 42, force_field: str = "MMFF94") -> tuple[Chem.Mol, dict]:
    molecules, metadata=generate_conformers(smiles,seed,1,force_field); return molecules[0],metadata[0]
