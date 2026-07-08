"""Lightweight source-integrity audit for Patch 10.10.

This module deliberately performs no reference mission, animation rendering,
Word construction or delivery packaging.  It checks only versioned source,
configuration and import contracts before any expensive production command is
allowed to proceed.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import json
import pkgutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from aquaskim.legacy_registry import REFERENCE_ALLOWED_MODULES, legacy_module_names
from aquaskim.paths import DIRECTORIES, PROJECT_ROOT, ensure_runtime_directories, relative_to_root


AUDIT_JSON = DIRECTORIES["logs"] / "patch10_10_source_integrity_audit.json"
AUDIT_MARKDOWN = DIRECTORIES["reports"] / "patch10_10_source_integrity_audit.md"


def _yaml_files() -> list[Path]:
    return sorted(DIRECTORIES["config"].rglob("*.yaml"))


def audit_yaml_parse() -> dict[str, Any]:
    """Parse every versioned YAML configuration file without executing a model."""
    rows: list[dict[str, object]] = []
    for path in _yaml_files():
        try:
            with path.open("r", encoding="utf-8") as handle:
                loaded = yaml.safe_load(handle)
            if loaded is None:
                raise ValueError("YAML document is empty")
            rows.append({"path": relative_to_root(path), "status": "PASS", "root_type": type(loaded).__name__})
        except Exception as exc:  # pragma: no cover - defensive audit path
            rows.append({"path": relative_to_root(path), "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
    passed = all(row["status"] == "PASS" for row in rows)
    return {"name": "yaml_parse", "passed": passed, "files": rows}


def _package_modules() -> list[str]:
    package_dir = PROJECT_ROOT / "src" / "aquaskim"
    return sorted(f"aquaskim.{item.name}" for item in pkgutil.iter_modules([str(package_dir)]) if not item.name.startswith("__"))


def audit_imports() -> dict[str, Any]:
    """Import every package module; import-time work must remain lightweight."""
    rows: list[dict[str, object]] = []
    for module_name in _package_modules():
        try:
            importlib.import_module(module_name)
            rows.append({"module": module_name, "status": "PASS"})
        except Exception as exc:  # pragma: no cover - failure is reported in json
            rows.append({"module": module_name, "status": "FAIL", "error": f"{type(exc).__name__}: {exc}"})
    passed = all(row["status"] == "PASS" for row in rows)
    return {"name": "import_audit", "passed": passed, "modules": rows}


def _imports_in_source(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def audit_reference_isolation() -> dict[str, Any]:
    """Prove that the reference path does not import quota-based modules."""
    legacy = legacy_module_names()
    source_modules = {
        "aquaskim.mission_plant": PROJECT_ROOT / "src" / "aquaskim" / "mission_plant.py",
        "aquaskim.mission_quality": PROJECT_ROOT / "src" / "aquaskim" / "mission_quality.py",
        "aquaskim.maneuver_validation": PROJECT_ROOT / "src" / "aquaskim" / "maneuver_validation.py",
        "aquaskim.phase10_6": PROJECT_ROOT / "src" / "aquaskim" / "phase10_6.py",
        "aquaskim.phase10_7": PROJECT_ROOT / "src" / "aquaskim" / "phase10_7.py",
        "aquaskim.phase10_8": PROJECT_ROOT / "src" / "aquaskim" / "phase10_8.py",
        "aquaskim.reference_fidelity": PROJECT_ROOT / "src" / "aquaskim" / "reference_fidelity.py",
        "aquaskim.phase10_11": PROJECT_ROOT / "src" / "aquaskim" / "phase10_11.py",
    }
    module_rows: list[dict[str, object]] = []
    for name, path in source_modules.items():
        imports = _imports_in_source(path)
        prohibited = sorted(item for item in legacy if item in imports)
        module_rows.append({"module": name, "path": relative_to_root(path), "prohibited_imports": prohibited, "status": "PASS" if not prohibited else "FAIL"})

    script_path = PROJECT_ROOT / "scripts" / "build_reference_project.bat"
    script_text = script_path.read_text(encoding="utf-8").lower()
    prohibited_tokens = ["run_patch_08", "run_patch_09", "run_patch_10.bat", "configure_and_build", "user_profile"]
    script_hits = [token for token in prohibited_tokens if token in script_text]
    script_row = {
        "script": relative_to_root(script_path),
        "prohibited_tokens": script_hits,
        "status": "PASS" if not script_hits else "FAIL",
    }
    allowed_imports = sorted(REFERENCE_ALLOWED_MODULES)
    passed = all(row["status"] == "PASS" for row in module_rows) and script_row["status"] == "PASS"
    return {
        "name": "reference_path_isolation",
        "passed": passed,
        "reference_allowed_modules": allowed_imports,
        "legacy_quota_modules": sorted(legacy),
        "module_checks": module_rows,
        "entrypoint_check": script_row,
    }


def audit_release_disabled() -> dict[str, Any]:
    """Confirm Word, delivery ZIP and final-release scripts cannot run accidentally."""
    scripts = [
        PROJECT_ROOT / "scripts" / "run_patch_10.bat",
        PROJECT_ROOT / "scripts" / "run_final_reproducible_build.bat",
        PROJECT_ROOT / "scripts" / "open_final_deliverables.bat",
    ]
    rows: list[dict[str, object]] = []
    for path in scripts:
        text = path.read_text(encoding="utf-8").lower()
        disabled = "release build disabled" in text or "final delivery disabled" in text
        rows.append({"script": relative_to_root(path), "status": "PASS" if disabled else "FAIL", "release_disabled_marker": disabled})
    return {"name": "release_disabled", "passed": all(row["status"] == "PASS" for row in rows), "scripts": rows}


def build_audit_report() -> dict[str, Any]:
    ensure_runtime_directories()
    checks = [audit_yaml_parse(), audit_imports(), audit_reference_isolation(), audit_release_disabled()]
    return {
        "patch": "Patch 10.10 — Source Integrity Recovery and Reference-Path Consolidation",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": [
            "YAML parsing", "module import audit", "reference-path legacy isolation", "release-build disablement",
        ],
        "explicitly_not_run": [
            "Reference mission simulation", "GIF/MP4 rendering", "Word report generation", "submission ZIP generation", "release build",
        ],
        "checks": checks,
        "status": "PASS" if all(bool(item["passed"]) for item in checks) else "FAIL",
    }


def write_audit_report(report: dict[str, Any]) -> tuple[Path, Path]:
    AUDIT_JSON.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Patch 10.10 — Source Integrity Audit",
        "",
        f"- Timestamp (UTC): `{report['timestamp_utc']}`",
        f"- Overall status: `{report['status']}`",
        "- Explicitly not run: reference mission, GIF/MP4 rendering, Word report, delivery ZIP, release build.",
        "",
        "## Checks",
    ]
    for check in report["checks"]:
        lines.append(f"- **{check['name']}**: `{'PASS' if check['passed'] else 'FAIL'}`")
    lines.extend([
        "",
        "## Reference-path policy",
        "The reference path is limited to the capacity-, energy-, time-, safety- and coverage-based mission implementation. Historical quota-based modules remain in source for traceability but are not reference-build dependencies.",
    ])
    AUDIT_MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return AUDIT_JSON, AUDIT_MARKDOWN


def _print_check(check: dict[str, Any]) -> None:
    print(f"[{ 'OK' if check['passed'] else 'FAIL'}] {check['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AquaSkim-Sim lightweight source integrity audit")
    parser.add_argument("command", nargs="?", choices=("yaml", "imports", "reference", "release", "report"), default="report")
    args = parser.parse_args(argv)
    dispatch = {
        "yaml": audit_yaml_parse,
        "imports": audit_imports,
        "reference": audit_reference_isolation,
        "release": audit_release_disabled,
    }
    if args.command == "report":
        report = build_audit_report()
        json_path, markdown_path = write_audit_report(report)
        print("=" * 72)
        print("AquaSkim-Sim | Patch 10.10 Source Integrity Audit")
        print("=" * 72)
        for check in report["checks"]:
            _print_check(check)
        print(f"JSON report : {relative_to_root(json_path)}")
        print(f"Markdown    : {relative_to_root(markdown_path)}")
        print(f"Status      : {report['status']}")
        print("=" * 72)
        return 0 if report["status"] == "PASS" else 1
    result = dispatch[args.command]()
    _print_check(result)
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
