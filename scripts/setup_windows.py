"""Offline per-user installer validation for the Windows distribution."""
from __future__ import annotations
import hashlib, json, os, platform, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; LOG=ROOT/"setup.log"; REPORT=ROOT/"setup_report.json"; VENV=ROOT/".venv"; WHEELS=ROOT/"wheelhouse"
def note(message):
    print(message); LOG.write_text((LOG.read_text(encoding="utf-8") if LOG.exists() else "")+message+"\n",encoding="utf-8")
def run(command):
    note("RUN: "+" ".join(map(str,command))); done=subprocess.run(command,cwd=ROOT,text=True,capture_output=True,shell=False,check=False); note(done.stdout); note(done.stderr)
    if done.returncode: raise RuntimeError(f"Command failed with exit code {done.returncode}")
def main():
    started=time.time(); report={"version":"1.4.0","platform":platform.platform(),"architecture":platform.machine(),"python_bootstrap":sys.executable,"status":"running"}; LOG.write_text("ZHU MolEnergy Workbench offline setup\n",encoding="utf-8")
    try:
        if os.name!="nt" or platform.machine().lower() not in {"amd64","x86_64"}: raise RuntimeError("Windows x64 is required")
        if not WHEELS.is_dir() or not list(WHEELS.glob("*.whl")): raise RuntimeError("Offline wheelhouse is missing or empty")
        test=ROOT/".setup_write_test"; test.write_text("ok"); test.unlink()
        if not (VENV/"Scripts"/"python.exe").is_file(): run([sys.executable,"-m","venv",str(VENV)])
        python=VENV/"Scripts"/"python.exe"
        run([str(python),"-m","pip","install","--no-index","--find-links",str(WHEELS),"setuptools==80.9.0","wheel==0.45.1"])
        run([str(python),"-m","pip","install","--no-index","--find-links",str(WHEELS),"-r",str(ROOT/"requirements-windows-lock.txt")])
        run([str(python),"-m","pip","install","--no-index","--find-links",str(WHEELS),"--no-build-isolation",str(ROOT)])
        smoke="from jpcb_energy.registry import discover_models; from jpcb_energy.workbench import predict_with_bundle; from pathlib import Path; m=discover_models(Path.cwd()); r=predict_with_bundle('C=CC(=O)N',m['v1.0.0-vacuum-reference']); print(len(m),r['prediction'])"
        done=subprocess.run([str(python),"-c",smoke],cwd=ROOT,text=True,capture_output=True,check=True); report.update({"official_models_loaded":int(done.stdout.split()[0]),"smoke_prediction_Eh":float(done.stdout.split()[1])})
        subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ROOT/"Install_ZHU_MolEnergy_Desktop_Shortcut.ps1")],cwd=ROOT,check=True)
        report.update({"status":"passed","venv_python":str(python),"duration_seconds":time.time()-started,"wheel_count":len(list(WHEELS.glob('*.whl')))})
    except Exception as exc: report.update({"status":"failed","error":str(exc),"duration_seconds":time.time()-started}); REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8"); note(f"ERROR: {exc}"); return 1
    REPORT.write_text(json.dumps(report,indent=2),encoding="utf-8"); note("All offline setup, model-load and smoke-prediction checks passed."); return 0
if __name__=="__main__": raise SystemExit(main())
