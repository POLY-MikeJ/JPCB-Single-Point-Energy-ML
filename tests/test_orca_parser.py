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

