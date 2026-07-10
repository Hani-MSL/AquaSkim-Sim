from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]


def test_reference_design_is_fixed_and_noninteractive() -> None:
    text = (ROOT / "scripts" / "run_from_zero_to_delivery.bat").read_text(
        encoding="utf-8"
    ).lower()
    assert "input(" not in text
    assert "run_patch_" not in text
    assert "python -m aquaskim.rebuild_from_zero" in text


def test_reference_registry_has_rationale_for_every_parameter() -> None:
    registry = yaml.safe_load(
        (ROOT / "config" / "parameter_registry.yaml").read_text(encoding="utf-8")
    )
    entries = registry["parameters"]
    assert len(entries) >= 12
    for entry in entries:
        assert entry["id"]
        assert entry["rationale"]
        assert entry["verification"]
        assert entry["unit"]


def test_reference_design_prohibits_collection_quota_as_termination_policy() -> None:
    text = (ROOT / "config" / "reference_design.yaml").read_text(
        encoding="utf-8"
    ).lower()
    assert "fixed collection-count quota is prohibited" in text
