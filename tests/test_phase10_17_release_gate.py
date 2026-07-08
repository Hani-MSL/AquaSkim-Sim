from __future__ import annotations

from aquaskim import __version__
from aquaskim.integrity_audit import audit_release_disabled
from aquaskim.phase10_6 import _settings
from aquaskim.reference_design import load_reference_configuration
from aquaskim.release_gate import load_release_gate_spec


def test_release_gate_contract_is_candidate_only_and_preserves_limits() -> None:
    spec = load_release_gate_spec()
    assert spec["identifier"] == "AQUASKIM-REL-GATE-01"
    assert spec["release_controls"]["final_scripts_must_remain_disabled"] is True
    classes = set(spec["curation_contract"]["required_claim_classes"])
    assert {"validated", "boundary", "controlled_failure"}.issubset(classes)
    assert "does not convert" in str(spec["model_boundary"])


def test_effective_reference_configuration_removes_legacy_max_collections() -> None:
    config = load_reference_configuration()
    assert "max_collections" not in config.data["autonomy"]
    low = {**config.data, "autonomy": {**config.data["autonomy"], "max_collections": 1}}
    high = {**config.data, "autonomy": {**config.data["autonomy"], "max_collections": 999}}
    assert _settings(low) == _settings(high)
    assert not hasattr(_settings(low), "max_collections")
    assert _settings(low).target_quota == 0


def test_canonical_version_is_held_in_reference_configuration() -> None:
    config = load_reference_configuration()
    assert config.project_version == __version__
    assert __version__.count(".") == 2


def test_release_scripts_remain_disabled_at_engineering_candidate_stage() -> None:
    audit = audit_release_disabled()
    assert audit["passed"] is True
