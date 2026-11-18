"""Auditable local GFN2-xTB jobs with complete raw-output preservation."""
from __future__ import annotations
import csv, hashlib, html, json, os, re, shutil, subprocess, time, uuid, zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from rdkit import Chem
from rdkit.Chem import rdMolDescriptors
from rdkit.Geometry import Point3D
from .conformer import conformer_mol, conformer_sdf, conformer_xyz, generate_conformers

EH_TO_EV=27.211386245988; EH_TO_KJ_MOL=2625.4996394799; EH_TO_KCAL_MOL=627.5094740631
SUPPORTED_ALPB={"acetone","acetonitrile","aniline","benzaldehyde","benzene","ch2cl2","chcl3","cs2","dioxane","dmf","dmso","ether","ethylacetate","furane","hexandecane","hexane","methanol","nitromethane","octanol","woctanol","phenol","toluene","thf","water"}
OPT_LEVELS={"crude","sloppy","loose","normal","tight","verytight","extreme"}; FLOAT=r"[-+]?\d+(?:\.\d+)?(?:[EeDd][-+]?\d+)?"

@dataclass(frozen=True)
class XTBInstallation:
    available: bool; executable: str|None; version: str|None; message: str; source: str|None=None

def _num(v): return float(v.replace("D","E").replace("d","e")) if v is not None else None
def _last(pattern,text):
    values=re.findall(pattern,text,re.I|re.M); return _num(values[-1]) if values else None

def software_root()->Path:
    configured=os.environ.get("ZHU_MOLENERGY_ROOT")
    if configured: return Path(configured).expanduser().resolve()
    cwd=Path.cwd().resolve()
    if (cwd/"runtime").is_dir() or (cwd/"Start_ZHU_MolEnergy.bat").is_file(): return cwd
    return Path(__file__).resolve().parents[2]

def user_config_path()->Path:
    override=os.environ.get("ZHU_MOLENERGY_CONFIG")
    if override: return Path(override).expanduser().resolve()
    base=Path(os.environ.get("LOCALAPPDATA") or Path.home()/"AppData"/"Local")
    return base/"ZHU MolEnergy Workbench"/"config.json"

def load_saved_xtb_path()->str|None:
    try:
        value=json.loads(user_config_path().read_text(encoding="utf-8")).get("xtb_executable")
        return str(value).strip() if value else None
    except (OSError,json.JSONDecodeError,AttributeError): return None

def xtb_environment(executable: str|Path,base: dict|None=None)->dict:
    """Return an xTB-ready child environment without changing the parent process."""
    executable=Path(executable).resolve(); env=dict(base or os.environ)
    env["PATH"]=str(executable.parent)+os.pathsep+env.get("PATH","")
    share_candidates=(executable.parent/"share"/"xtb",executable.parent.parent/"share"/"xtb")
    share=next((path for path in share_candidates if path.is_dir()),None)
    if share: env["XTBPATH"]=str(share.resolve())
    env["XTB_EXE"]=str(executable)
    return env

def _configured_locations(root: Path):
    files=(root/"config"/"xtb_locations.json",root/"config"/"xtb_locations.local.json")
    for config in files:
        try: entries=json.loads(config.read_text(encoding="utf-8")).get("known_locations",[])
        except (OSError,json.JSONDecodeError,AttributeError): continue
        for entry in entries:
            raw=entry.get("path") if isinstance(entry,dict) else entry
            if not raw: continue
            expanded=os.path.expandvars(str(raw)); path=Path(expanded).expanduser()
            if not path.is_absolute(): path=root/path
            if any(mark in str(path) for mark in "*?["):
                yield from sorted(path.parent.glob(path.name))
            else: yield path

def _verify_xtb(path: str|Path,source: str)->XTBInstallation:
    candidate=Path(path).expanduser()
    if not candidate.is_file(): return XTBInstallation(False,str(candidate),None,f"Configured xTB path does not exist: {candidate}",source)
    try:
        resolved=str(candidate.resolve())
        run=subprocess.run([resolved,"--version"],capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=15,shell=False,check=False,env=xtb_environment(resolved)); output=(run.stdout+"\n"+run.stderr).strip()
        if run.returncode: return XTBInstallation(False,resolved,None,f"xTB version check failed ({run.returncode}): {output[-300:]}",source)
        if "xtb version" not in output.lower(): return XTBInstallation(False,resolved,None,"Executable did not report an xTB version.",source)
        version=next((line.strip() for line in output.splitlines() if "xtb version" in line.lower()),"version not reported")
        return XTBInstallation(True,resolved,version,f"Verified local xTB executable ({source})",source)
    except (OSError,subprocess.TimeoutExpired) as exc: return XTBInstallation(False,str(candidate),None,f"xTB verification failed: {exc}",source)

def save_xtb_path(path: str|Path)->XTBInstallation:
    installation=_verify_xtb(path,"user-saved path")
    if not installation.available: return installation
    config=user_config_path(); config.parent.mkdir(parents=True,exist_ok=True)
    payload={"schema_version":1,"xtb_executable":installation.executable,"verified_version":installation.version,"saved_at_utc":datetime.now(timezone.utc).isoformat()}
    config.write_text(json.dumps(payload,indent=2),encoding="utf-8")
    return installation

def detect_xtb(explicit_path: str|Path|None=None)->XTBInstallation:
    """Discover xTB in deterministic order and verify every candidate by execution."""
    root=software_root(); candidates=[]
    # 1. Installer-owned runtime always wins and makes desktop launches self-contained.
    candidates.append((root/"runtime"/"xtb"/"xtb.exe","bundled runtime"))
    # 2. An explicit UI value, the persisted user choice, then the documented env override.
    if explicit_path: candidates.append((Path(explicit_path).expanduser(),"user-selected path"))
    saved=load_saved_xtb_path()
    if saved: candidates.append((Path(saved).expanduser(),"user-saved path"))
    if os.environ.get("XTB_EXE"): candidates.append((Path(os.environ["XTB_EXE"]).expanduser(),"XTB_EXE environment"))
    # 3. System/user PATH.
    on_path=shutil.which("xtb.exe") or shutil.which("xtb")
    if on_path: candidates.append((Path(on_path),"system PATH"))
    # 4. Site-specific locations are data, never private paths embedded in source.
    candidates.extend((path,"configured known location") for path in _configured_locations(root))
    seen=set(); failures=[]
    for path,source in candidates:
        key=os.path.normcase(str(path.resolve(strict=False)))
        if key in seen: continue
        seen.add(key)
        if not path.is_file(): continue
        installation=_verify_xtb(path,source)
        if installation.available: return installation
        failures.append(installation.message)
    detail=f" Last verification error: {failures[-1]}" if failures else ""
    return XTBInstallation(False,None,None,"xTB was not found or could not be executed. Bundled runtime, saved path, PATH, and configured locations were checked."+detail,None)

def build_xtb_command(executable,input_name,charge,unpaired_electrons,solvent=None,opt_level="tight",complete_output=False):
    if Path(input_name).name!=input_name or not input_name.lower().endswith(".xyz"): raise ValueError("xTB input must be a simple local .xyz filename")
    if not(-10<=int(charge)<=10 and 0<=int(unpaired_electrons)<=10): raise ValueError("Charge or unpaired-electron count is outside the allowed range")
    if opt_level not in OPT_LEVELS: raise ValueError(f"Unsupported optimization level: {opt_level}")
    command=[str(executable),input_name,"--gfn","2","--opt",opt_level,"--chrg",str(int(charge)),"--uhf",str(int(unpaired_electrons))]
    if complete_output: command += ["--json","--pop","--wbo","--dipole"]
    if solvent:
        solvent=solvent.lower().strip()
        if solvent not in SUPPORTED_ALPB: raise ValueError(f"Unsupported ALPB solvent: {solvent}")
        command += ["--alpb",solvent]
    return command

def validate_electronic_state(mol,charge,unpaired):
    electrons=sum(a.GetAtomicNum() for a in mol.GetAtoms())-int(charge); warnings=[]
    if electrons<1: warnings.append("Requested charge produces a non-positive electron count.")
    if (electrons-int(unpaired))%2: warnings.append(f"Electron-count parity mismatch: {electrons} electrons and {unpaired} unpaired electron(s).")
    if int(unpaired)>electrons: warnings.append("Unpaired-electron count exceeds electron count.")
    return warnings

def _floats(path):
    values=[]
    if path.is_file():
        for token in path.read_text(encoding="utf-8",errors="replace").split():
            try: values.append(float(token.replace("D","E")))
            except ValueError: pass
    return values
def _wbo(path):
    rows=[]
    if path.is_file():
        for line in path.read_text(encoding="utf-8",errors="replace").splitlines():
            f=line.split()
            try:
                if len(f)>=3: rows.append({"atom_i":int(f[0]),"atom_j":int(f[1]),"wiberg_bond_order":float(f[2])})
            except ValueError: pass
    return rows

def parse_xtb_output(text,job_dir):
    job_dir=Path(job_dir); cycle=[_num(v) for v in re.findall(r"\*\s*total energy\s*:\s*(%s)\s*Eh"%FLOAT,text,re.I)]; final_values=[_num(v) for v in re.findall(r"(?:\||::)?\s*total energy\s+(%s)\s*Eh"%FLOAT,text,re.I)]
    initial=cycle[0] if cycle else (final_values[0] if final_values else None); final=final_values[-1] if final_values else (cycle[-1] if cycle else None); optimized=job_dir/"xtbopt.xyz"
    conv=re.findall(r"GEOMETRY OPTIMIZATION CONVERGED AFTER\s+(\d+)\s+ITERATIONS",text,re.I) or (["0"] if re.search(r"GEOMETRY OPTIMIZATION CONVERGED",text,re.I) else []); scc=re.findall(r"convergence criteria satisfied after\s+(\d+)\s+iterations",text,re.I)
    homo=re.findall(r"(%s)\s+(%s)\s*\(HOMO\)"%(FLOAT,FLOAT),text,re.I); lumo=re.findall(r"(%s)\s+(%s)\s*\(LUMO\)"%(FLOAT,FLOAT),text,re.I); dip=re.findall(r"molecular dipole:.*?full:\s*(%s)\s+(%s)\s+(%s)\s+(%s)"%(FLOAT,FLOAT,FLOAT,FLOAT),text,re.I|re.S)
    terms={label.strip():{"value":_num(value),"unit":unit} for label,value,unit in re.findall(r"::\s*([^:\n]+?)\s+(%s)\s+(Eh|eV|e)\s*::"%FLOAT,text,re.I)}
    warnings=list(dict.fromkeys(line.strip() for line in text.splitlines() if re.search(r"\bWARNING\b|failed|not converged|abnormal",line,re.I)))
    xjson=None; jp=job_dir/"xtbout.json"
    if jp.is_file():
        raw_json=jp.read_text(encoding="utf-8",errors="replace")
        try: xjson=json.loads(raw_json)
        except json.JSONDecodeError:
            repaired=[]
            for line in raw_json.splitlines():
                if '"program call"' in line:
                    value=line.split(":",1)[1].strip().rstrip(",").strip('"'); line='   "program call": '+json.dumps(value)+','
                repaired.append(line)
            try: xjson=json.loads("\n".join(repaired)); warnings.append("xTB emitted an unescaped Windows program-call string; parser repaired that field while retaining the original xtbout.json.")
            except json.JSONDecodeError: warnings.append("xtbout.json could not be decoded; original file retained.")
    result={"converged":bool(conv) and optimized.is_file(),"optimization_cycles":int(conv[-1]) if conv else None,"scc_converged":bool(scc),"final_scc_iterations":int(scc[-1]) if scc else None,"initial_energy_Eh":initial,"final_energy_Eh":final,"energy_change_Eh":final-initial if final is not None and initial is not None else None,"energy_occurrences":len(cycle)+len(final_values),"final_gradient_norm_Eh_per_bohr":_last(r"(?:\||::)\s*(?:GRADIENT NORM|gradient norm)\s+(%s)\s*Eh/(?:a0|α)"%FLOAT,text),"final_displacement_norm_bohr":_last(r"displ\. norm\s*:\s*(%s)\s*α"%FLOAT,text),"maximum_displacement_bohr":_last(r"maximum displ\.\s*:\s*(%s)\s*α"%FLOAT,text),"homo_energy_Eh":_num(homo[-1][0]) if homo else None,"homo_energy_eV":_num(homo[-1][1]) if homo else None,"lumo_energy_Eh":_num(lumo[-1][0]) if lumo else None,"lumo_energy_eV":_num(lumo[-1][1]) if lumo else None,"homo_lumo_gap_eV":_last(r"HOMO-LUMO (?:GAP|gap)\s+(%s)\s*eV"%FLOAT,text),"fermi_level_Eh":_last(r"Fermi-level\s+(%s)\s*Eh"%FLOAT,text),"fermi_level_eV":_last(r"Fermi-level\s+%s\s*Eh\s+(%s)\s*eV"%(FLOAT,FLOAT),text),"total_charge_e":_last(r"::\s*total charge\s+(%s)\s*e"%FLOAT,text),"dipole_x_D":_num(dip[-1][0]) if dip else None,"dipole_y_D":_num(dip[-1][1]) if dip else None,"dipole_z_D":_num(dip[-1][2]) if dip else None,"dipole_total_D":_num(dip[-1][3]) if dip else None,"molecular_mass_u":_last(r"molecular mass/u\s*:\s*(%s)"%FLOAT,text),"optimization_level_reported":(re.findall(r"optimization level\s+(\w+)",text,re.I)or[None])[-1],"energy_convergence_Eh":_last(r"energy convergence\s+(%s)\s*Eh"%FLOAT,text),"gradient_convergence_Eh_per_bohr":_last(r"grad\. convergence\s+(%s)\s*Eh/"%FLOAT,text),"electronic_temperature_K":_last(r"electronic temp\.\s+(%s)\s*K"%FLOAT,text),"energy_terms":terms,"atomic_partial_charges_e":_floats(job_dir/"charges"),"wiberg_bond_orders":_wbo(job_dir/"wbo"),"xtbout_json":xjson,"warnings":warnings,"optimized_xyz":str(optimized) if optimized.is_file() else None}
    for key in ("initial_energy_Eh","final_energy_Eh","energy_change_Eh"):
        value=result[key]; stem=key[:-3]; result[stem+"eV"]=value*EH_TO_EV if value is not None else None; result[stem+"kJ_mol"]=value*EH_TO_KJ_MOL if value is not None else None; result[stem+"kcal_mol"]=value*EH_TO_KCAL_MOL if value is not None else None
    return result

def molecule_from_xyz(template,xyz_path):
    lines=Path(xyz_path).read_text(encoding="utf-8",errors="replace").splitlines(); count=int(lines[0]); coords=lines[2:2+count]
    if count!=template.GetNumAtoms() or len(coords)!=count: raise ValueError("xTB optimized atom count does not match input")
    result=Chem.Mol(template); conf=Chem.Conformer(count)
    for i,line in enumerate(coords):
        f=line.split()
        if len(f)<4 or f[0].lower()!=result.GetAtomWithIdx(i).GetSymbol().lower(): raise ValueError("xTB atom ordering/elements do not match input")
        conf.SetAtomPosition(i,Point3D(float(f[1]),float(f[2]),float(f[3])))
    result.RemoveAllConformers(); result.AddConformer(conf,assignId=True); return result

def _flatten(prefix,value,rows):
    if isinstance(value,dict):
        for key,item in value.items(): _flatten(f"{prefix}.{key}" if prefix else key,item,rows)
    elif isinstance(value,list): rows.append({"parameter":prefix,"value":json.dumps(value),"unit":""})
    else: rows.append({"parameter":prefix,"value":"Not reported by this calculation" if value is None else value,"unit":""})
def _exports(directory,metadata,result):
    combined={"provenance":metadata,"results":result,"conversion_constants":{"Eh_to_eV":EH_TO_EV,"Eh_to_kJ_mol":EH_TO_KJ_MOL,"Eh_to_kcal_mol":EH_TO_KCAL_MOL}}; (directory/"xtb_results.json").write_text(json.dumps(combined,indent=2),encoding="utf-8"); rows=[]; _flatten("",combined,rows)
    with (directory/"xtb_results.csv").open("w",newline="",encoding="utf-8-sig") as h: w=csv.DictWriter(h,fieldnames=["parameter","value","unit"]); w.writeheader(); w.writerows(rows)
    (directory/"xtb_summary.txt").write_text("\n".join(["ZHU MolEnergy Workbench — Complete GFN2-xTB Results",f"Job: {metadata['job_id']}",f"Status: {metadata['status']}",f"xTB: {metadata['xtb_version']}",f"Method/solvent: GFN2-xTB / {metadata['solvation_model']}",f"Charge/UHF/multiplicity: {metadata['charge']}/{metadata['unpaired_electrons']}/{metadata['spin_multiplicity']}",f"Initial/final/change (Eh): {result.get('initial_energy_Eh')} / {result.get('final_energy_Eh')} / {result.get('energy_change_Eh')}"]),encoding="utf-8")
    table="".join(f"<tr><th>{html.escape(str(r['parameter']))}</th><td>{html.escape(str(r['value']))}</td></tr>" for r in rows); (directory/"xtb_report.html").write_text(f"<!doctype html><meta charset=utf-8><style>body{{font:14px sans-serif;max-width:1100px;margin:auto}}th,td{{border:1px solid #ccd;padding:5px}}table{{border-collapse:collapse}}</style><h1>Complete GFN2-xTB Results</h1><p>GFN2-xTB is distinct from ORCA DFT and GPR predictions.</p><table>{table}</table>",encoding="utf-8")
    manifest=[]
    for p in sorted(directory.iterdir()):
        if p.is_file() and p.name not in {"sha256_manifest.csv","complete_xtb_job.zip"}: manifest.append({"file":p.name,"bytes":p.stat().st_size,"sha256":hashlib.sha256(p.read_bytes()).hexdigest()})
    with (directory/"sha256_manifest.csv").open("w",newline="",encoding="utf-8") as h: w=csv.DictWriter(h,fieldnames=["file","bytes","sha256"]); w.writeheader(); w.writerows(manifest)
    with zipfile.ZipFile(directory/"complete_xtb_job.zip","w",zipfile.ZIP_DEFLATED) as z:
        for p in sorted(directory.iterdir()):
            if p.is_file() and p.name!="complete_xtb_job.zip": z.write(p,p.name)

def run_xtb(smiles,executable,jobs_root,charge,unpaired_electrons,solvent=None,timeout_seconds=900,max_atoms=250,seed=42,opt_level="tight",threads=1):
    installation=detect_xtb(executable)
    if not installation.available: raise RuntimeError(installation.message)
    molecules,info=generate_conformers(smiles,seed,1,"MMFF94"); molecule=molecules[0]
    if molecule.GetNumAtoms()>max_atoms: raise ValueError(f"Molecule has {molecule.GetNumAtoms()} atoms; limit {max_atoms}")
    warnings=validate_electronic_state(molecule,charge,unpaired_electrons)
    if warnings: raise ValueError(" ".join(warnings))
    job_id=f"xtb-{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:8]}"; directory=Path(jobs_root).resolve()/job_id; directory.mkdir(parents=True,exist_ok=False); (directory/"input.xyz").write_text(conformer_xyz(molecule,"RDKit illustrative input geometry"),encoding="utf-8"); (directory/"input.sdf").write_text(conformer_sdf(molecule,"RDKit input; atom order retained"),encoding="utf-8")
    command=build_xtb_command(installation.executable or executable,"input.xyz",charge,unpaired_electrons,solvent,opt_level,complete_output=True); canonical=Chem.MolToSmiles(Chem.RemoveHs(molecule),canonical=True,isomericSmiles=True); elements=Counter(a.GetSymbol() for a in molecule.GetAtoms()); start=datetime.now(timezone.utc); timer=time.perf_counter()
    metadata={"job_id":job_id,"status":"running","canonical_smiles":canonical,"molecular_formula":rdMolDescriptors.CalcMolFormula(Chem.RemoveHs(molecule)),"atom_count_including_hydrogen":molecule.GetNumAtoms(),"element_composition":dict(sorted(elements.items())),"formal_charge_from_smiles":Chem.GetFormalCharge(Chem.RemoveHs(molecule)),"charge":int(charge),"unpaired_electrons":int(unpaired_electrons),"spin_multiplicity":int(unpaired_electrons)+1,"method":"GFN2-xTB","optimization_level":opt_level,"solvation_model":f"ALPB({solvent})" if solvent else "gas phase","command":command,"executable":installation.executable,"xtb_version":installation.version,"input_geometry_provenance":info[0],"random_seed":seed,"threads":threads,"environment":{"OMP_NUM_THREADS":str(threads),"MKL_NUM_THREADS":str(threads)},"timeout_seconds":timeout_seconds,"start_time_utc":start.isoformat(),"job_directory":str(directory)}; (directory/"job.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    try:
        environment=xtb_environment(installation.executable or executable); environment.update({"OMP_NUM_THREADS":str(threads),"MKL_NUM_THREADS":str(threads)})
        done=subprocess.run(command,cwd=directory,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout_seconds,shell=False,check=False,env=environment); log=done.stdout+("\n[stderr]\n"+done.stderr if done.stderr else ""); (directory/"xtb.log").write_text(log,encoding="utf-8"); result=parse_xtb_output(log,directory)
        if result["optimized_xyz"]:
            optimized=molecule_from_xyz(molecule,result["optimized_xyz"]); (directory/"optimized.sdf").write_text(conformer_sdf(optimized,"GFN2-xTB optimized geometry"),encoding="utf-8"); (directory/"optimized.mol").write_text(conformer_mol(optimized,"GFN2-xTB optimized geometry"),encoding="utf-8"); result.update({"optimized_sdf":str(directory/"optimized.sdf"),"optimized_mol":str(directory/"optimized.mol")})
        metadata.update({"status":"completed" if done.returncode==0 and result["converged"] else "failed","exit_code":done.returncode})
    except subprocess.TimeoutExpired as exc:
        raw=(exc.stdout or b""); raw=raw if isinstance(raw,str) else raw.decode("utf-8","replace"); (directory/"xtb.log").write_text(raw+f"\nTIMEOUT after {timeout_seconds} seconds\n",encoding="utf-8"); result=parse_xtb_output(raw,directory); result["warnings"].append(f"Timed out after {timeout_seconds} seconds"); metadata.update({"status":"timeout","exit_code":None})
    metadata.update({"end_time_utc":datetime.now(timezone.utc).isoformat(),"runtime_seconds":time.perf_counter()-timer}); (directory/"job.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8"); _exports(directory,metadata,result)
    return {**metadata,**result,"job_dir":str(directory),"results_json":str(directory/"xtb_results.json"),"results_csv":str(directory/"xtb_results.csv"),"summary_txt":str(directory/"xtb_summary.txt"),"html_report":str(directory/"xtb_report.html"),"raw_log":str(directory/"xtb.log"),"job_zip":str(directory/"complete_xtb_job.zip"),"manifest":str(directory/"sha256_manifest.csv")}

def rdkit_optimize(smiles,seed=42,force_field="MMFF94"):
    molecules,metadata=generate_conformers(smiles,seed,1,force_field); return molecules[0],metadata[0]
