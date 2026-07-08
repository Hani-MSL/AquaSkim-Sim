from pathlib import Path


def test_phase08_source_compiles_before_runtime_import() -> None:
    """Guard against invalid f-string expressions and similar parse-time failures."""
    source_path = Path(__file__).resolve().parents[1] / "src" / "aquaskim" / "phase08.py"
    source = source_path.read_text(encoding="utf-8")
    compile(source, str(source_path), "exec")
