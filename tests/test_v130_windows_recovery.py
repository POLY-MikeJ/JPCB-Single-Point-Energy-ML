"""Regression coverage for the v1.3.0 Windows startup recovery."""

from __future__ import annotations

import importlib.util
import socket
import sys
from pathlib import Path

import streamlit
from PIL import Image


ROOT=Path(__file__).parents[1]


def _launcher():
    spec=importlib.util.spec_from_file_location("zhu_launcher",ROOT/"scripts"/"launcher.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


def test_python_streamlit_and_application_entry_integrity():
    assert Path(sys.executable).is_file()
    assert tuple(map(int,streamlit.__version__.split(".")[:2])) >= (1,45)
    source=(ROOT/"src"/"jpcb_energy"/"app.py").read_text(encoding="utf-8")
    compile(source,str(ROOT/"src"/"jpcb_energy"/"app.py"),"exec")
    assert "st.set_page_config" in source and "PRODUCT_NAME" in source


def test_cache_strategy_avoids_streamlit_source_hashing_regression():
    source=(ROOT/"src"/"jpcb_energy"/"app.py").read_text(encoding="utf-8")
    assert "@st.cache_resource" not in source and "@st.cache_data" not in source
    assert "@lru_cache(maxsize=1)" in source and "@lru_cache(maxsize=8)" in source


def test_application_preflight_renders_all_acceptance_pages():
    spec=importlib.util.spec_from_file_location("zhu_preflight",ROOT/"scripts"/"preflight_app.py")
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    for page in ["Predict","Molecular Explorer","Data Cleaning & Outlier Removal","About & Citation"]:
        result=module.render(page)
        assert result["passed"],result


def test_port_conflict_selection_and_error_log_detection(tmp_path):
    launcher=_launcher()
    with socket.socket(socket.AF_INET,socket.SOCK_STREAM) as occupied:
        occupied.bind(("127.0.0.1",0)); port=occupied.getsockname()[1]
        assert launcher.free_port(port,attempts=10) != port
    launcher.LOG=tmp_path/"startup.log"; launcher.LOG.write_text("TokenError: EOF in multi-line string",encoding="utf-8")
    assert launcher.log_exception()=="TokenError:"


def test_local_resource_paths_startup_scripts_and_transparent_mascot():
    start=(ROOT/"Start_ZHU_MolEnergy.bat").read_text(encoding="utf-8")
    installer=(ROOT/"Install_ZHU_MolEnergy_Desktop_Shortcut.ps1").read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in start and "launcher.py" in start and "--foreground" in start
    assert "Start_ZHU_MolEnergy.bat" in installer and "ZHU MolEnergy Workbench.lnk" in installer
    asset=ROOT/"assets"/"zhu_molenergy_scientist.png"; assert asset.is_file()
    with Image.open(asset) as image:
        assert image.format=="PNG" and image.mode=="RGBA"
        assert image.getextrema()[3][0]==0 and image.width>=1000 and image.height>=1000


def test_launcher_shutdown_and_duplicate_detection_primitives():
    launcher=_launcher()
    assert launcher.pid_alive(__import__("os").getpid())
    assert launcher.health(65534,timeout=.05) is False
    assert "taskkill" in (ROOT/"scripts"/"launcher.py").read_text(encoding="utf-8")
