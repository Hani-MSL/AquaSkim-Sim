from __future__ import annotations

from pathlib import Path

from aquaskim.integrity_audit import (
    audit_imports,
    audit_reference_isolation,
    audit_release_disabled,
    audit_yaml_parse,
)
from aquaskim.legacy_registry import legacy_module_names
from aquaskim.paths import PROJECT_ROOT
from aquaskim.phase02 import run_phase02


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


def test_release_scripts_are_explicitly_disabled() -> None:
    for filename in ("run_patch_10.bat", "run_final_reproducible_build.bat", "open_final_deliverables.bat"):
        text = (PROJECT_ROOT / "scripts" / filename).read_text(encoding="utf-8").lower()
        assert "release build disabled" in text or "final delivery disabled" in text


def test_reference_build_runs_integrity_before_reference_media_generation() -> None:
    text = (PROJECT_ROOT / "scripts" / "build_reference_project.bat").read_text(encoding="utf-8").lower()
    assert "run_patch_10_10_source_integrity" in text
    assert text.index("run_patch_10_10_source_integrity") < text.index("run_patch_10_9")
