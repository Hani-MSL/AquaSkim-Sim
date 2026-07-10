from aquaskim.paths import PROJECT_ROOT


def test_reproduction_entrypoint_uses_fixed_reference_rebuild() -> None:
    script = (PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.bat").read_text(
        encoding="utf-8"
    ).lower()
    assert "python -m aquaskim.rebuild_from_zero" in script
    assert "environment.yml" in script
    assert "run_patch_" not in script


def test_public_modelling_and_validation_documentation_exists() -> None:
    document = PROJECT_ROOT / "docs" / "MODELING_AND_VALIDATION.md"
    assert document.exists()
    text = document.read_text(encoding="utf-8")
    assert "Low-speed dynamics" in text
    assert "Validation strategy" in text
