import hashlib, json, zipfile
from pathlib import Path
import pytest
from jpcb_energy.registry import discover_models
from jpcb_energy.xtb import build_xtb_command, parse_xtb_output

ROOT=Path(__file__).parents[1]

def test_actual_xtb_671pre_fixture_complete_fields():
    folder=ROOT/"tests"/"data"/"xtb_success_6.7.1pre"; raw=(folder/"xtb.log").read_text(encoding="utf-8")
    parsed=parse_xtb_output(raw,folder)
    assert parsed["converged"] and parsed["optimization_cycles"]==7
    assert parsed["final_energy_Eh"]==pytest.approx(-11.394339303574)
    assert parsed["homo_energy_eV"]==pytest.approx(-11.1900)
    assert parsed["lumo_energy_eV"]==pytest.approx(1.6969)
    assert parsed["homo_lumo_gap_eV"]==pytest.approx(12.886953837502)
    assert parsed["dipole_total_D"]==pytest.approx(1.997)
    assert len(parsed["atomic_partial_charges_e"])==9 and parsed["wiberg_bond_orders"]
    assert parsed["xtbout_json"]["xtb version"].startswith("6.7.1pre")

def test_incomplete_and_future_output_are_not_fabricated_or_discarded():
    path=ROOT/"tests"/"data"/"xtb_failure_incomplete.log"; raw=path.read_text(encoding="utf-8")
    parsed=parse_xtb_output(raw,path.parent)
    assert not parsed["converged"] and parsed["final_energy_Eh"] is None
    assert parsed["warnings"] and "UNKNOWN FUTURE OUTPUT LINE" in raw

def test_complete_command_requests_supported_machine_outputs():
    command=build_xtb_command("xtb.exe","input.xyz",0,0,"water","tight",complete_output=True)
    for flag in ["--json","--pop","--wbo","--dipole","--alpb"]: assert flag in command

def test_all_official_model_hashes_load_and_match_metadata():
    models=discover_models(ROOT); assert len(models)==6
    for entry in models.values():
        metadata=entry["metadata"]; expected=metadata.get("model_sha256")
        if expected: assert hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest()==expected

def test_offline_installer_contract_and_xtb_binary_is_staged_not_tracked():
    batch=(ROOT/"Setup_ZHU_MolEnergy.bat").read_text(encoding="utf-8")
    setup=(ROOT/"scripts"/"setup_windows.py").read_text(encoding="utf-8")
    assert "python-3.13.5-amd64.exe" in batch and "certutil" in batch and "InstallAllUsers=0" in batch
    assert "--no-index" in setup and "discover_models" in setup and "smoke_prediction_Eh" in setup
    assert not (ROOT/"runtime"/"xtb"/"xtb.exe").exists()
    stager=(ROOT/"scripts"/"stage_xtb_runtime.py").read_text(encoding="utf-8")
    assert "EXPECTED_ARCHIVE_SHA256" in stager and "COPYING.LESSER" in stager

def test_actual_job_zip_reopens_when_validation_artifact_available():
    jobs=ROOT/"local_jobs"/"xtb_v140_validation"
    archives=list(jobs.glob("*/complete_xtb_job.zip")) if jobs.exists() else []
    if not archives: pytest.skip("Local actual-run evidence is not part of the public source tree")
    with zipfile.ZipFile(archives[0]) as z:
        names=set(z.namelist()); assert {"input.xyz","input.sdf","xtb.log","job.json","xtb_results.json","xtb_results.csv","xtb_summary.txt","xtbopt.xyz","optimized.sdf","optimized.mol","sha256_manifest.csv"}<=names
        json.loads(z.read("xtb_results.json"))
