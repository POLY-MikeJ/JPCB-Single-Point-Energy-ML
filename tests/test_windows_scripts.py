from pathlib import Path


def test_windows_entrypoints_exist_and_reference_venv():
    root = Path(__file__).resolve().parents[1]
    for name in ["install_windows.bat", "run_windows.bat", "run_cli_example.bat"]:
        text = (root / name).read_text(encoding="utf-8")
        assert ".venv" in text

