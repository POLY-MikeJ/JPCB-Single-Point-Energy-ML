from pathlib import Path
from jpcb_energy.orca_parser import parse_orca


def test_representative_orca_output():
    sample = Path(__file__).parent / "data" / "representative_output.txt"
    result = parse_orca(sample)
    assert result["normal_termination"] is True
    assert result["task_type"] == "frequency"
    assert result["final_single_point_energy_Eh"] == -100.123456789
    assert result["zero_point_energy_Eh"] == 0.05
    assert result["imaginary_frequency_count"] == 1


def test_utf16_cpcm_metadata_and_abnormal_output(tmp_path):
    content = """Program Version 6.1.1
|  1> ! B3LYP 6-311++G(d,p) Freq TightSCF cpcm(water)
* xyz -1 1
Epsilon                                         ...      80.1510
FINAL SINGLE POINT ENERGY      -200.123456000
  0:        10.00 cm**-1
****ORCA TERMINATED NORMALLY****
"""
    utf16 = tmp_path / "water_utf16.out"
    utf16.write_text(content, encoding="utf-16")
    parsed = parse_orca(utf16)
    assert parsed["solvent"] == "water"
    assert parsed["dielectric_constant"] == 80.151
    assert parsed["method"] == "B3LYP" and parsed["basis_set"] == "6-311++G(d,p)"
    assert parsed["charge"] == -1 and parsed["multiplicity"] == 1
    assert parsed["normal_termination"] is True

    abnormal = tmp_path / "abnormal.out"
    abnormal.write_text("! B3LYP def2-SVP Opt\nFINAL SINGLE POINT ENERGY -1.0\n", encoding="utf-8")
    failed = parse_orca(abnormal)
    assert failed["normal_termination"] is False
    assert failed["task_type"] == "optimization"

