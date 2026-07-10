"""Lightweight source-integrity audit for the public reproducible workflow.

The audit performs no mission simulation, media rendering, Word generation, or
package assembly. It validates versioned configuration, import contracts,
reference-path isolation, and the public execution entrypoints before expensive
production steps begin.
"""
from __future__ import annotations

import argparse
import ast
import importlib
import json
import pkgutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from aquaskim.legacy_registry import REFERENCE_ALLOWED_MODULES, legacy_module_names
from aquaskim.paths import DIRECTORIES, PROJECT_ROOT, ensure_runtime_directories, relative_to_root

AUDIT_JSON = DIRECTORIES["logs"] / "source_integrity_audit.json"
AUDIT_MARKDOWN = DIRECTORIES["reports"] / "source_integrity_audit.md"

PUBLIC_ENTRYPOINTS = (
    PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.bat",
    PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.sh",
    PROJECT_ROOT / "scripts" / "run_tests.bat",
)


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
            rows.append(
                {
                    "path": relative_to_root(path),
                    "status": "PASS",
                    "root_type": type(loaded).__name__,
                }
            )
        except Exception as exc:  # pragma: no cover - defensive audit path
            rows.append(
                {
                    "path": relative_to_root(path),
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "name": "yaml_parse",
        "passed": all(row["status"] == "PASS" for row in rows),
        "files": rows,
    }


def _package_modules() -> list[str]:
    package_dir = PROJECT_ROOT / "src" / "aquaskim"
    return sorted(
        f"aquaskim.{item.name}"
        for item in pkgutil.iter_modules([str(package_dir)])
        if not item.name.startswith("__")
    )


def audit_imports() -> dict[str, Any]:
    """Import every package module; import-time work must remain lightweight."""
    rows: list[dict[str, object]] = []
    for module_name in _package_modules():
        try:
            importlib.import_module(module_name)
            rows.append({"module": module_name, "status": "PASS"})
        except Exception as exc:  # pragma: no cover - failure is reported in JSON
            rows.append(
                {
                    "module": module_name,
                    "status": "FAIL",
                    "error": f"{type(exc).__name__}: {exc}",
                }
            )
    return {
        "name": "import_audit",
        "passed": all(row["status"] == "PASS" for row in rows),
        "modules": rows,
    }


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
    """Verify that the reference workflow does not import legacy quota modules."""
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
        module_rows.append(
            {
                "module": name,
                "path": relative_to_root(path),
                "prohibited_imports": prohibited,
                "status": "PASS" if not prohibited else "FAIL",
            }
        )

    entrypoint = PROJECT_ROOT / "scripts" / "run_from_zero_to_delivery.bat"
    text = entrypoint.read_text(encoding="utf-8").lower() if entrypoint.exists() else ""
    prohibited_tokens = ["run_patch_", "configure_and_build", "user_profile"]
    hits = [token for token in prohibited_tokens if token in text]
    entrypoint_row = {
        "script": relative_to_root(entrypoint),
        "exists": entrypoint.exists(),
        "prohibited_tokens": hits,
        "status": "PASS" if entrypoint.exists() and not hits else "FAIL",
    }

    passed = all(row["status"] == "PASS" for row in module_rows) and entrypoint_row["status"] == "PASS"
    return {
        "name": "reference_path_isolation",
        "passed": passed,
        "reference_allowed_modules": sorted(REFERENCE_ALLOWED_MODULES),
        "legacy_quota_modules": sorted(legacy),
        "module_checks": module_rows,
        "entrypoint_check": entrypoint_row,
    }


def audit_release_disabled() -> dict[str, Any]:
    """Compatibility API: validate that only public entrypoints are required."""
    rows: list[dict[str, object]] = []
    for path in PUBLIC_ENTRYPOINTS:
        exists = path.exists()
        text = path.read_text(encoding="utf-8").lower() if exists else ""
        clean = "run_patch_" not in text and "chatgpt" not in text and "openai" not in text
        rows.append(
            {
                "script": relative_to_root(path),
                "exists": exists,
                "status": "PASS" if exists and path.stat().st_size > 0 and clean else "FAIL",
                "public_entrypoint": clean,
            }
        )
    return {
        "name": "public_entrypoints",
        "passed": all(row["status"] == "PASS" for row in rows),
        "scripts": rows,
    }


def build_audit_report() -> dict[str, Any]:
    ensure_runtime_directories()
    checks = [
        audit_yaml_parse(),
        audit_imports(),
        audit_reference_isolation(),
        audit_release_disabled(),
    ]
    return {
        "audit": "AquaSkim-Sim source integrity and reproducibility",
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": [
            "YAML parsing",
            "module import audit",
            "reference-path isolation",
            "public entrypoint validation",
        ],
        "explicitly_not_run": [
            "Reference mission simulation",
            "GIF/MP4 rendering",
            "Word report generation",
            "delivery ZIP generation",
        ],
        "checks": checks,
        "status": "PASS" if all(bool(item["passed"]) for item in checks) else "FAIL",
    }


def write_audit_report(report: dict[str, Any]) -> tuple[Path, Path]:
    AUDIT_JSON.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# Source Integrity Audit",
        "",
        f"- Timestamp (UTC): `{report['timestamp_utc']}`",
        f"- Overall status: `{report['status']}`",
        "- Expensive simulation, media, report, and delivery steps are not run by this audit.",
        "",
        "## Checks",
    ]
    for check in report["checks"]:
        lines.append(f"- **{check['name']}**: `{'PASS' if check['passed'] else 'FAIL'}`")
    lines.extend(
        [
            "",
            "## Reference-path policy",
            "The reference workflow uses the capacity-, energy-, time-, safety-, and coverage-based mission implementation. Legacy quota modules remain isolated from the public rebuild path.",
        ]
    )
    AUDIT_MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return AUDIT_JSON, AUDIT_MARKDOWN


def _print_check(check: dict[str, Any]) -> None:
    print(f"[{'OK' if check['passed'] else 'FAIL'}] {check['name']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AquaSkim-Sim lightweight source integrity audit")
    parser.add_argument(
        "command",
        nargs="?",
        choices=("yaml", "imports", "reference", "release", "report"),
        default="report",
    )
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
        print("AquaSkim-Sim | Source Integrity Audit")
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
