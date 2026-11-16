import json
import subprocess
from pathlib import Path

import pandas as pd
import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

from jpcb_energy.conformer import conformer_rmsd, generate_conformers
from jpcb_energy.data_qc import composition_oof_residuals, parse_geometry, reversible_inclusion
from jpcb_energy.visualization import DrawSettings, molecule_png_bytes, molecule_properties, molecule_svg
from jpcb_energy.xtb import XTBInstallation, build_xtb_command, parse_xtb_output, run_xtb


ROOT = Path(__file__).resolve().parents[1]


def test_original_predict_page_path_has_no_streamlit_exception():
    app = AppTest.from_file(str(ROOT / "src" / "jpcb_energy" / "app.py"), default_timeout=30).run()
    assert not app.exception
    app.button(key="predict_button").click().run(timeout=30)
    assert not app.exception
    assert any("-244.583" in metric.value for metric in app.metric)


def test_2d_settings_preserve_identity_and_exports_scale():
    smiles = "C[C@H](O)C(=O)[O-]"
    identity = molecule_properties(smiles)
    settings = DrawSettings(style="monochrome", atom_indices=True, atom_maps=True, show_hydrogens=True, smarts="[O-]", background="transparent", width=480, height=320, rotation=45)
    svg = molecule_svg(smiles, settings)
    png = molecule_png_bytes(smiles, settings=settings, scale=2)
    assert "<svg" in svg and len(png) > 2000
    image = Image.open(__import__("io").BytesIO(png))
    assert image.size == (960, 640)
    assert molecule_properties(smiles)["isomeric_smiles"] == identity["isomeric_smiles"]


def test_multiple_conformers_are_seeded_and_atom_correspondence_is_checked():
    first, _ = generate_conformers("CCCO", seed=17, count=3, force_field="MMFF94s")
    second, _ = generate_conformers("CCCO", seed=17, count=3, force_field="MMFF94s")
    assert len(first) >= 1 and conformer_rmsd(first[0], second[0]) == pytest.approx(0.0, abs=1e-7)
    different, _ = generate_conformers("CCN", seed=17, count=1)
    with pytest.raises(ValueError): conformer_rmsd(first[0], different[0])


def test_xtb_command_is_argument_list_and_output_parser(tmp_path):
    command = build_xtb_command(r"C:\Tools\xtb.exe", "input.xyz", -1, 1, "water")
    assert command == [r"C:\Tools\xtb.exe", "input.xyz", "--gfn", "2", "--opt", "tight", "--chrg", "-1", "--uhf", "1", "--alpb", "water"]
    with pytest.raises(ValueError): build_xtb_command("xtb.exe", "../bad.xyz", 0, 0)
    (tmp_path / "xtbopt.xyz").write_text("1\nmock\nH 0 0 0\n")
    parsed = parse_xtb_output("GEOMETRY OPTIMIZATION CONVERGED\n TOTAL ENERGY -5.123456 Eh", tmp_path)
    assert parsed["converged"] and parsed["final_energy_Eh"] == -5.123456 and parsed["initial_energy_Eh"] == -5.123456


def test_xtb_runner_uses_safe_subprocess_and_isolated_job(monkeypatch, tmp_path):
    calls = []
    class Result:
        returncode = 0
        stdout = "GEOMETRY OPTIMIZATION CONVERGED\n TOTAL ENERGY -10.0 Eh"
        stderr = ""
    def fake_detect(path): return XTBInstallation(True, str(tmp_path / "xtb.exe"), "mock 1.0", "verified")
    def fake_run(command, **kwargs):
        calls.append((command, kwargs)); directory=Path(kwargs["cwd"]); (directory / "xtbopt.xyz").write_text((directory / "input.xyz").read_text()); return Result()
    monkeypatch.setattr("jpcb_energy.xtb.detect_xtb", fake_detect)
    monkeypatch.setattr("jpcb_energy.xtb.subprocess.run", fake_run)
    result = run_xtb("C", str(tmp_path / "xtb.exe"), tmp_path / "jobs", 0, 0, timeout_seconds=5)
    assert result["status"] == "completed" and result["method"] == "GFN2-xTB"
    assert Path(result["optimized_sdf"]).is_file()
    assert calls[0][1]["shell"] is False and isinstance(calls[0][0], list)
    assert Path(result["optimized_xyz"]).parent.parent == (tmp_path / "jobs").resolve()


def test_geometry_identity_composition_reference_and_reversible_inclusion(tmp_path):
    inp = tmp_path / "echoed.inp"
    inp.write_text("| 9> * xyz 1 1\n| 10> C 0.0 0.0 0.0\n| 11> H 0.0 0.0 1.1\n| 12> *\n")
    parsed = parse_geometry(inp)
    assert parsed["geometry_charge"] == 1 and parsed["atom_count"] == 2
    frame = pd.DataFrame({"record_key":[f"x:{i}" for i in range(10)],"record_id":[str(i) for i in range(10)],"canonical_smiles":[f"C{i}" for i in range(10)],"element_counts":[json.dumps({"C":i+1,"H":2*i+4}) for i in range(10)],"charge":[0]*10,"final_single_point_energy_Eh":[-40*(i+1) for i in range(10)],"qc_status":["verified"]*9+["invalid_calculation"]})
    assert composition_oof_residuals(frame).notna().all()
    initial = reversible_inclusion(frame)
    assert not bool(initial.iloc[-1].include_verified_strict)
    restored = reversible_inclusion(frame, pd.DataFrame({"record_key":["x:9"],"review_decision":["restore"],"reviewed_by":["reviewer"]}))
    assert bool(restored.iloc[-1].include_verified_strict)


def test_desktop_launchers_use_project_venv_and_safe_stop_state():
    launcher = (ROOT / "Launch_JPCB_Workbench.bat").read_text(encoding="utf-8")
    stop = (ROOT / "Stop_JPCB_Workbench.bat").read_text(encoding="utf-8")
    source = (ROOT / "scripts" / "launcher.py").read_text(encoding="utf-8")
    assert "%~dp0.venv\\Scripts\\python.exe" in launcher
    assert "taskkill" not in stop.lower() and "launcher.py\" stop" in stop
    assert '["taskkill","/PID",str(pid),"/T","/F"]' in source and "taskkill /IM python" not in source
    completed = subprocess.run([str(ROOT / ".venv" / "Scripts" / "python.exe"), str(ROOT / "scripts" / "launcher.py"), "diagnose"], capture_output=True, text=True, check=True)
    assert json.loads(completed.stdout)["python_exists"] is True
