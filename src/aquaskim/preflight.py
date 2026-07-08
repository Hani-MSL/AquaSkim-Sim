from __future__ import annotations

import json
import platform
import shutil
import sys
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any

from aquaskim.config import load_base_configuration, load_scenario
from aquaskim.paths import DIRECTORIES, PROJECT_ROOT, ensure_runtime_directories, relative_to_root

EXPECTED_SCENARIOS = ("calm_water", "lateral_current", "obstacles", "low_battery")
REQUIRED_DISTRIBUTIONS = ("numpy", "scipy", "pandas", "matplotlib", "imageio", "python-docx", "plotly", "PyYAML")


def _package_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for package in REQUIRED_DISTRIBUTIONS:
        try:
            versions[package] = version(package)
        except PackageNotFoundError:
            versions[package] = "NOT FOUND"
    return versions


def _mass_total_kg(components: list[dict[str, Any]]) -> float:
    return sum(float(component["mass_kg"]) for component in components)


def build_preflight_report() -> dict[str, Any]:
    """Run non-destructive checks and collect a JSON-serializable health report."""
    ensure_runtime_directories()
    config = load_base_configuration()

    scenario_checks: dict[str, str] = {}
    for scenario_name in EXPECTED_SCENARIOS:
        scenario = load_scenario(scenario_name)
        scenario_checks[scenario_name] = str(scenario["scenario"]["title_fa"])

    required_directories = {
        name: {
            "path": relative_to_root(path),
            "exists": path.exists(),
        }
        for name, path in DIRECTORIES.items()
    }

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "project_root": str(PROJECT_ROOT),
        "python": {
            "version": sys.version.replace("\n", " "),
            "executable": sys.executable,
            "platform": platform.platform(),
        },
        "tools": {
            "ffmpeg_available": shutil.which("ffmpeg") is not None,
        },
        "packages": _package_versions(),
        "configuration": {
            "file": relative_to_root(config.source_path),
            "project_name": config.project_name,
            "project_version": config.project_version,
            "hull_dimensions_m": {
                "length": config.hull_length_m,
                "width": config.hull_width_m,
                "height": config.hull_height_m,
            },
            "dry_mass_budget_kg": round(_mass_total_kg(config.mass_components), 6),
            "component_count": len(config.mass_components),
        },
        "scenarios": scenario_checks,
        "directories": required_directories,
    }


def write_preflight_report(report: dict[str, Any]) -> Path:
    destination = DIRECTORIES["logs"] / "phase_01_preflight.json"
    destination.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return destination


def print_preflight_summary(report: dict[str, Any], saved_to: Path) -> None:
    print("=" * 72)
    print("AquaSkim-Sim | Phase 01 Preflight")
    print("=" * 72)
    print(f"Project root : {report['project_root']}")
    print(f"Python       : {report['python']['version'].split(' ')[0]}")
    print(f"Executable   : {report['python']['executable']}")
    print(f"FFmpeg       : {'FOUND' if report['tools']['ffmpeg_available'] else 'NOT FOUND'}")
    print(f"Project      : {report['configuration']['project_name']} v{report['configuration']['project_version']}")
    print(f"Hull (m)     : {report['configuration']['hull_dimensions_m']}")
    print(f"Dry mass (kg): {report['configuration']['dry_mass_budget_kg']}")
    print(f"Components   : {report['configuration']['component_count']}")
    print("Scenarios    : " + ", ".join(report["scenarios"].keys()))
    missing = [name for name, details in report["directories"].items() if not details["exists"]]
    print("Directories  : " + ("OK" if not missing else f"MISSING: {', '.join(missing)}"))
    print(f"Report saved : {relative_to_root(saved_to)}")
    print("=" * 72)


def run_preflight() -> int:
    report = build_preflight_report()
    saved_to = write_preflight_report(report)
    print_preflight_summary(report, saved_to)

    missing_packages = [
        name for name, package_version in report["packages"].items()
        if package_version == "NOT FOUND"
    ]
    if missing_packages:
        print(f"[ERROR] Required packages are missing: {', '.join(missing_packages)}")
        return 1

    if not report["tools"]["ffmpeg_available"]:
        print("[WARNING] ffmpeg is not visible in PATH. MP4 generation will be checked again later.")

    print("[OK] Phase 01 environment and project scaffold are healthy.")
    return 0
