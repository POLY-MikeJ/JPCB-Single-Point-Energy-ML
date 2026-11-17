#!/usr/bin/env python
"""Windows launcher and safe stopper for ZHU MolEnergy Workbench."""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
APP = ROOT / "src" / "jpcb_energy" / "app.py"
STATE_DIR = ROOT / "local_jobs" / "zhu_molenergy_launcher"
STATE = STATE_DIR / "zhu_molenergy_launcher_state.json"
LOG = STATE_DIR / "zhu_molenergy_streamlit.log"
PREFLIGHT = ROOT / "scripts" / "preflight_app.py"


def health(port: int, timeout: float = 0.8) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=timeout) as response:
            return response.status == 200 and b"ok" in response.read(64).lower()
    except Exception:
        return False


def pid_alive(pid: int) -> bool:
    if os.name == "nt":
        completed = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], capture_output=True, text=True, shell=False, check=False)
        return completed.returncode == 0 and f'"{pid}"' in completed.stdout
    try: os.kill(pid, 0); return True
    except OSError: return False


def listening_pid(port: int) -> int | None:
    """Return the exact Windows PID listening on the requested local port."""
    completed = subprocess.run(["netstat", "-ano", "-p", "tcp"], capture_output=True, text=True, shell=False, check=False)
    for line in completed.stdout.splitlines():
        fields = line.split()
        if len(fields) >= 5 and fields[0].upper() == "TCP" and fields[1].endswith(f":{port}") and fields[3].upper() == "LISTENING":
            try: return int(fields[4])
            except ValueError: continue
    return None


def process_description(pid: int | None) -> str:
    if not pid: return "unknown process"
    completed=subprocess.run(["tasklist","/FI",f"PID eq {pid}","/FO","CSV","/NH"],capture_output=True,text=True,shell=False,check=False)
    first=completed.stdout.strip().splitlines()
    return first[0] if first else f"PID {pid}"


def load_state() -> dict | None:
    try: return json.loads(STATE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError): return None


def free_port(start: int = 8501, attempts: int = 50) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try: sock.bind(("127.0.0.1", port)); return port
            except OSError: continue
    raise RuntimeError("No free localhost port was found in the configured range")


def preflight() -> tuple[bool, str]:
    """Render the real app once so Streamlit script errors cannot masquerade as healthy."""
    try:
        completed=subprocess.run([str(PYTHON),str(PREFLIGHT),"--startup"],cwd=ROOT,capture_output=True,text=True,shell=False,check=False,timeout=120)
    except subprocess.TimeoutExpired as exc:
        return False,f"Application preflight timed out after {exc.timeout} seconds"
    detail=(completed.stdout+completed.stderr).strip()
    return completed.returncode==0,detail


def log_exception() -> str | None:
    try: content=LOG.read_text(encoding="utf-8",errors="replace")
    except OSError: return None
    markers=("Traceback (most recent call last)","TokenError:","ModuleNotFoundError:","ImportError:","SyntaxError:")
    return next((marker for marker in markers if marker in content),None)


def mark_state(status: str, **extra) -> None:
    state=load_state() or {}; state.update({"status":status,"updated_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),**extra})
    STATE_DIR.mkdir(parents=True,exist_ok=True); STATE.write_text(json.dumps(state,indent=2),encoding="utf-8")


def supervise(process: subprocess.Popen, port: int) -> int:
    print("Launcher remains attached to Streamlit. Press Ctrl+C or use Stop_ZHU_MolEnergy.bat to stop cleanly.")
    try:
        code=process.wait(); mark_state("stopped",exit_code=code); return code
    except KeyboardInterrupt:
        print("Stopping launcher-owned Streamlit process...")
        completed=subprocess.run(["taskkill","/PID",str(process.pid),"/T"],capture_output=True,text=True,shell=False,check=False)
        if completed.returncode and process.poll() is None: process.terminate()
        try: process.wait(timeout=15)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        mark_state("stopped_by_ctrl_c",exit_code=130); return 130


def start(foreground: bool = False) -> int:
    if not PYTHON.is_file():
        print(f"ERROR: Project interpreter not found: {PYTHON}"); return 2
    if not APP.is_file():
        print(f"ERROR: Application entry point not found: {APP}"); return 2
    if not PREFLIGHT.is_file():
        print(f"ERROR: Startup preflight not found: {PREFLIGHT}"); return 2
    ok,detail=preflight()
    if not ok:
        print("ERROR: Application preflight failed; Streamlit was not started.")
        print(detail)
        return 3
    previous = load_state()
    if previous and previous.get("project_root") == str(ROOT) and pid_alive(int(previous.get("pid", -1))) and health(int(previous.get("port", 0))):
        url=previous["url"]; print(f"ZHU MolEnergy Workbench is already running: {url}"); webbrowser.open(url); return 0
    port_8501_pid=listening_pid(8501)
    if port_8501_pid:
        print(f"NOTICE: Port 8501 is occupied by {process_description(port_8501_pid)}. The process will not be terminated.")
        port=free_port(8502)
    else: port=8501
    url=f"http://127.0.0.1:{port}"; STATE_DIR.mkdir(parents=True,exist_ok=True)
    command=[str(PYTHON),"-m","streamlit","run",str(APP),"--server.address=127.0.0.1",f"--server.port={port}","--server.headless=true","--browser.gatherUsageStats=false","--server.fileWatcherType=none"]
    creationflags=0 if foreground else getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0)|getattr(subprocess,"DETACHED_PROCESS",0)
    LOG.write_text(f"ZHU MolEnergy Workbench startup log\nStarted: {time.strftime('%Y-%m-%dT%H:%M:%S%z')}\nPreflight: passed\nCommand: {' '.join(command)}\n\n",encoding="utf-8")
    with LOG.open("a",encoding="utf-8") as log:
        process=subprocess.Popen(command,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,creationflags=creationflags,shell=False,close_fds=True)
    state={"pid":process.pid,"bootstrap_pid":process.pid,"port":port,"url":url,"project_root":str(ROOT),"python":str(PYTHON),"command":command,"foreground":foreground,"status":"starting","started_at":time.strftime("%Y-%m-%dT%H:%M:%S%z"),"log":str(LOG)}; STATE.write_text(json.dumps(state,indent=2),encoding="utf-8")
    print(f"Starting ZHU MolEnergy Workbench at {url}")
    for _ in range(90):
        if health(port):
            state["pid"] = listening_pid(port) or process.pid; STATE.write_text(json.dumps(state,indent=2),encoding="utf-8")
            webbrowser.open(url); time.sleep(2.0)
            marker=log_exception()
            if marker:
                print(f"ERROR: Application log contains {marker}. See {LOG}")
                subprocess.run(["taskkill","/PID",str(state["pid"]),"/T"],capture_output=True,text=True,shell=False,check=False)
                mark_state("failed_application_render",error_marker=marker); return 3
            state["status"]="ready"; STATE.write_text(json.dumps(state,indent=2),encoding="utf-8")
            print(f"Ready: {url} (server PID {state['pid']})")
            return supervise(process,port) if foreground else 0
        if process.poll() is not None: print(f"ERROR: Streamlit exited with code {process.returncode}. See {LOG}"); return 3
        time.sleep(0.5)
    process.terminate(); print(f"ERROR: Startup timed out. See {LOG}"); return 4


def stop() -> int:
    state=load_state()
    if not state or state.get("project_root") != str(ROOT): print("No launcher-owned workbench process is recorded."); return 0
    pid=int(state["pid"])
    if not pid_alive(pid): print("Recorded workbench process is no longer running."); return 0
    completed=subprocess.run(["taskkill","/PID",str(pid),"/T","/F"],capture_output=True,text=True,shell=False,check=False)
    if completed.returncode: print(f"ERROR: Could not stop launcher-owned PID {pid}: {completed.stderr.strip()}"); return completed.returncode
    print(f"Stopped launcher-owned workbench PID {pid}."); return 0


def diagnose() -> int:
    print(json.dumps({"project_root":str(ROOT),"python":str(PYTHON),"python_exists":PYTHON.is_file(),"app":str(APP),"app_exists":APP.is_file(),"state":load_state()},indent=2)); return 0


if __name__ == "__main__":
    parser=argparse.ArgumentParser(); parser.add_argument("action",nargs="?",choices=["start","stop","diagnose"],default="start"); parser.add_argument("--foreground",action="store_true",help="Keep the launcher attached so Ctrl+C and console close stop Streamlit")
    arguments=parser.parse_args(); raise SystemExit(start(arguments.foreground) if arguments.action=="start" else {"stop":stop,"diagnose":diagnose}[arguments.action]())
