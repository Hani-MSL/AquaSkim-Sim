from aquaskim.paths import PROJECT_ROOT


def test_interactive_reproduction_entrypoint_uses_configured_build() -> None:
    script = (PROJECT_ROOT / "scripts" / "configure_and_build.bat").read_text(encoding="utf-8").lower()
    assert "run-configured-build" in script
    assert "python -m aquaskim.cli configure" in script


def test_release_quality_documentation_exists() -> None:
    assert (PROJECT_ROOT / "docs" / "phases" / "phase_10_3" / "03_RELEASE_GATE.md").exists()
