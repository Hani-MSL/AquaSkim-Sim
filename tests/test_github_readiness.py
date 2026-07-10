from __future__ import annotations

from aquaskim.github_readiness import run_github_readiness_checks
from aquaskim.paths import PROJECT_ROOT


def test_public_github_readiness_checks_pass() -> None:
    checks = run_github_readiness_checks()
    failing = {check.name: check.detail for check in checks if not check.passed}
    assert failing == {}


def test_one_command_rebuild_entrypoint_is_documented() -> None:
    readme = (PROJECT_ROOT / "README.md").read_text(encoding="utf-8")
    script = PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.bat"
    assert script.exists()
    assert script.stat().st_size > 1_000
    assert "scripts\\run_from_zero_to_delivery.bat" in readme
    assert "AquaSkim-Sim_Final_Delivery_v1.6.21.zip" in readme


def test_public_metadata_template_does_not_commit_private_metadata() -> None:
    assert not (PROJECT_ROOT / "config" / "report_metadata.json").exists()
    assert (PROJECT_ROOT / "config" / "report_metadata.template.json").exists()
    assert not (PROJECT_ROOT / "config" / "user_profile.yaml").exists()
