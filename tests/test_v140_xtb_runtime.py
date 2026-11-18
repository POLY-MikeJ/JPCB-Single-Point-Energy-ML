import json, os
from pathlib import Path
import jpcb_energy.xtb as xtb

ROOT=Path(__file__).parents[1]

def test_bundled_runtime_has_highest_discovery_precedence(tmp_path,monkeypatch):
    bundled=tmp_path/"runtime"/"xtb"/"xtb.exe"; bundled.parent.mkdir(parents=True); bundled.write_bytes(b"test")
    monkeypatch.setenv("ZHU_MOLENERGY_ROOT",str(tmp_path)); monkeypatch.setenv("XTB_EXE",str(tmp_path/"other.exe"))
    monkeypatch.setattr(xtb,"_verify_xtb",lambda path,source:xtb.XTBInstallation(True,str(Path(path)),"xtb version test",source,source))
    found=xtb.detect_xtb(tmp_path/"explicit.exe")
    assert found.executable==str(bundled) and found.source=="bundled runtime"

def test_saved_user_path_roundtrip_uses_per_user_config(tmp_path,monkeypatch):
    executable=tmp_path/"xtb.exe"; executable.write_bytes(b"test"); config=tmp_path/"user-config.json"
    monkeypatch.setenv("ZHU_MOLENERGY_CONFIG",str(config))
    monkeypatch.setattr(xtb,"_verify_xtb",lambda path,source:xtb.XTBInstallation(True,str(Path(path).resolve()),"xtb version test",source,source))
    assert xtb.save_xtb_path(executable).available
    assert xtb.load_saved_xtb_path()==str(executable.resolve())
    assert json.loads(config.read_text(encoding="utf-8"))["xtb_executable"]==str(executable.resolve())

def test_xtb_child_environment_sets_private_dll_and_parameter_paths(tmp_path):
    executable=tmp_path/"xtb.exe"; executable.write_bytes(b""); share=tmp_path/"share"/"xtb"; share.mkdir(parents=True)
    env=xtb.xtb_environment(executable,{"PATH":"original"})
    assert env["PATH"].split(os.pathsep)[0]==str(tmp_path.resolve())
    assert env["XTBPATH"]==str(share.resolve()) and env["XTB_EXE"]==str(executable.resolve())

def test_known_locations_are_configuration_driven_and_public_safe():
    payload=json.loads((ROOT/"config"/"xtb_locations.json").read_text(encoding="utf-8"))
    serialized=json.dumps(payload)
    assert payload["known_locations"] and "F:\\" not in serialized and "C:\\Users" not in serialized

def test_launcher_exports_bundled_xtb_environment():
    launcher=(ROOT/"scripts"/"launcher.py").read_text(encoding="utf-8")
    batch=(ROOT/"Start_ZHU_MolEnergy.bat").read_text(encoding="utf-8")
    assert "configure_bundled_xtb" in launcher and 'runtime"/"xtb"/"xtb.exe' in launcher
    assert "runtime\\xtb\\xtb.exe" in batch and "XTBPATH" in batch and "XTB_EXE" in batch

def test_runtime_stager_pins_official_archive_and_licenses():
    source=(ROOT/"scripts"/"stage_xtb_runtime.py").read_text(encoding="utf-8")
    assert "043e578da4a7e114a4d584972959a875e3ffb9f2767a86723b95aa6719d28d9c" in source
    assert "COPYING.LESSER" in source and "corresponding-source" in source
