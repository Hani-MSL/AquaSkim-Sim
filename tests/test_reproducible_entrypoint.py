from pathlib import Path

from aquaskim.paths import PROJECT_ROOT


def test_bootstrap_entrypoint_is_interactive_and_not_final_report_runner() -> None:
    content = (PROJECT_ROOT / "scripts" / "bootstrap_and_build.bat").read_text(encoding="utf-8").lower()
    assert "configure_and_build" in content
    assert "run_patch_10" not in content


def test_phase09_2_runner_exists() -> None:
    assert (PROJECT_ROOT / "scripts" / "run_patch_09_2.bat").exists()
