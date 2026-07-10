from __future__ import annotations

from aquaskim.integrity_audit import (
    audit_imports,
    audit_reference_isolation,
    audit_release_disabled,
    audit_yaml_parse,
)
from aquaskim.legacy_registry import legacy_module_names
from aquaskim.phase02 import run_phase02
from aquaskim.rebuild_from_zero import _steps


def test_phase02_is_reconstructed_from_shared_design_configuration() -> None:
    artifacts = run_phase02()
    summary = artifacts.summary_json.read_text(encoding="utf-8")
    assert "Mechanical Architecture and Mass Properties" in summary
    assert artifacts.geometry_table.exists()
    assert artifacts.mass_budget_table.exists()
    assert artifacts.mass_cases_table.exists()
    assert artifacts.component_key_table.exists()


def test_reference_path_has_no_direct_import_of_quota_based_legacy_modules() -> None:
    result = audit_reference_isolation()
    assert result["passed"], result
    assert "aquaskim.phase08" in legacy_module_names()
    assert "aquaskim.autonomy" in legacy_module_names()


def test_lightweight_audits_pass_without_rendering_media_or_delivery() -> None:
    assert audit_yaml_parse()["passed"]
    assert audit_imports()["passed"]
    assert audit_release_disabled()["passed"]


def test_public_entrypoints_are_present_and_free_of_internal_workflow_markers() -> None:
    result = audit_release_disabled()
    assert result["name"] == "public_entrypoints"
    assert result["passed"]
    assert all(row["exists"] and row["public_entrypoint"] for row in result["scripts"])


def test_rebuild_runs_source_audit_before_generation_steps() -> None:
    names = [step.name for step in _steps()]
    assert names[:2] == ["clean", "source-audit"]
    assert names[-2:] == ["phase10-18", "phase10-19"]
