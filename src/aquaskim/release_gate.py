"""Engineering release-candidate gate for fixed-reference evidence.

This module is intentionally audit-only.  A passing result verifies that the
versioned source and curated evidence are internally consistent enough to begin
controlled Word-report construction.  It never enables a delivery ZIP, final
release build, distribution action or external-performance claim.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import shutil
import tomllib
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from aquaskim import __version__
from aquaskim.integrity_audit import (
    audit_imports,
    audit_reference_isolation,
    audit_release_disabled,
    audit_yaml_parse,
)
from aquaskim.paths import DIRECTORIES, PROJECT_ROOT, ensure_runtime_directories, relative_to_root
from aquaskim.phase10_6 import _settings
from aquaskim.reference_design import load_reference_configuration

GATE_JSON = DIRECTORIES["logs"] / "engineering_release_gate.json"
GATE_MARKDOWN = DIRECTORIES["reports"] / "engineering_release_gate.md"
GATE_TABLE = DIRECTORIES["tables"] / "engineering_release_gate_checks.csv"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _check(name: str, passed: bool, detail: str, **evidence: Any) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "detail": detail, "evidence": evidence}


def _load_yaml(path: Path) -> dict[str, Any]:
    parsed = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected YAML mapping: {relative_to_root(path)}")
    return parsed


def load_release_gate_spec() -> dict[str, Any]:
    """Load the versioned release-gate contract without running a model."""
    return _load_yaml(DIRECTORIES["config"] / "reference_release_gate.yaml")


def _read_json(path: Path) -> dict[str, Any]:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError(f"Expected JSON object: {relative_to_root(path)}")
    return parsed


def _canonical_version_check() -> dict[str, Any]:
    pyproject = PROJECT_ROOT / "pyproject.toml"
    readme = PROJECT_ROOT / "README_FA.md"
    reference_design = DIRECTORIES["config"] / "reference_design.yaml"
    metadata = tomllib.loads(pyproject.read_text(encoding="utf-8"))
    package_version = str(metadata["project"]["version"])
    reference_version = str(_load_yaml(reference_design)["overrides"]["project"]["version"])
    match = re.search(r"نسخهٔ سورس:\s*`([^`]+)`", readme.read_text(encoding="utf-8"))
    readme_version = match.group(1) if match else "<missing>"
    expected = __version__
    values = {
        "package": package_version,
        "module": expected,
        "reference_design": reference_version,
        "README_FA": readme_version,
    }
    passed = len(set(values.values())) == 1
    return _check(
        "canonical_version_contract",
        passed,
        "Canonical package, module, reference-design and README versions must agree.",
        versions=values,
    )


def _reference_policy_check() -> dict[str, Any]:
    """Verify that legacy quota compatibility cannot enter the reference runner."""
    config = load_reference_configuration()
    autonomy = config.data.get("autonomy", {})
    effective_key_absent = isinstance(autonomy, dict) and "max_collections" not in autonomy

    low_data = deepcopy(config.data)
    high_data = deepcopy(config.data)
    # Deliberately inject incompatible legacy values.  The reference settings
    # constructor must ignore them completely rather than treating them as a
    # fallback termination rule.
    low_data.setdefault("autonomy", {})["max_collections"] = 1
    high_data.setdefault("autonomy", {})["max_collections"] = 999
    low_settings = _settings(low_data)
    high_settings = _settings(high_data)

    same_settings = low_settings == high_settings
    no_runtime_quota = not hasattr(low_settings, "max_collections") and int(low_settings.target_quota) == 0
    policy = config.data.get("reference_mission", {}).get("validated_control_policy", {})
    current_policy = bool(policy.get("current_compensation_enabled", False))
    speed_threshold = float(policy.get("current_compensation_activation_speed_mps", -1.0))
    passed = effective_key_absent and same_settings and no_runtime_quota and current_policy and speed_threshold == 0.0
    return _check(
        "reference_policy_and_quota_isolation",
        passed,
        "The reference configuration removes max_collections and QualityMissionSettings receives no quota termination input.",
        effective_max_collections_present=not effective_key_absent,
        injected_legacy_values_produce_identical_settings=same_settings,
        quality_settings_has_max_collections=hasattr(low_settings, "max_collections"),
        quality_settings_target_quota=int(low_settings.target_quota),
        current_compensation_enabled=current_policy,
        current_compensation_activation_speed_mps=speed_threshold,
    )


def _upstream_integrity_checks() -> list[dict[str, Any]]:
    upstream = [audit_yaml_parse(), audit_imports(), audit_reference_isolation(), audit_release_disabled()]
    names = {
        "yaml_parse": "yaml_parse",
        "import_audit": "import_audit",
        "reference_path_isolation": "reference_path_isolation",
        "release_disabled": "release_scripts_still_disabled",
    }
    checks: list[dict[str, Any]] = []
    for result in upstream:
        name = str(result.get("name", "unknown"))
        checks.append(_check(names.get(name, name), bool(result.get("passed")), f"Delegated from source-integrity audit: {name}.", source_audit=result))
    return checks


def _required_evidence_check(spec: dict[str, Any]) -> dict[str, Any]:
    required = spec["required_evidence"]
    report_rows: list[dict[str, Any]] = []
    manifest_rows: list[dict[str, Any]] = []

    for raw in required["reports"]:
        path = PROJECT_ROOT / str(raw)
        exists = path.is_file() and path.stat().st_size > 0
        includes_boundary = False
        if exists:
            text = path.read_text(encoding="utf-8", errors="replace")
            includes_boundary = "Model boundary" in text or "model boundary" in text
        report_rows.append({"path": str(raw), "exists": exists, "has_model_boundary": includes_boundary})

    for raw in required["visual_manifests"]:
        path = PROJECT_ROOT / str(raw)
        exists = path.is_file() and path.stat().st_size > 0
        bool_checks: dict[str, bool] = {}
        status = "<missing>"
        parse_error = ""
        if exists:
            try:
                parsed = _read_json(path)
                status = str(parsed.get("status", "PASS"))
                bool_checks = {key: value for key, value in parsed.items() if key.startswith("all_") and isinstance(value, bool)}
            except Exception as exc:  # defensive audit path
                parse_error = f"{type(exc).__name__}: {exc}"
        manifest_rows.append({
            "path": str(raw), "exists": exists, "status": status,
            "all_boolean_checks": bool_checks,
            "parse_error": parse_error,
            "passed": exists and not parse_error and status == "PASS" and all(bool_checks.values()),
        })

    passed = all(item["exists"] and item["has_model_boundary"] for item in report_rows) and all(item["passed"] for item in manifest_rows)
    return _check(
        "required_reference_evidence",
        passed,
        "Every required report and visual-quality manifest must exist, be nonempty and retain a stated model boundary.",
        reports=report_rows,
        visual_manifests=manifest_rows,
    )


def _asset_integrity(source: Path, curated: Path, expected_hash: str) -> dict[str, Any]:
    source_exists = source.is_file()
    curated_exists = curated.is_file()
    source_hash = _sha256(source) if source_exists else ""
    curated_hash = _sha256(curated) if curated_exists else ""
    passed = source_exists and curated_exists and source_hash == curated_hash == expected_hash
    return {
        "source": relative_to_root(source),
        "curated": relative_to_root(curated),
        "source_exists": source_exists,
        "curated_exists": curated_exists,
        "source_sha256": source_hash,
        "curated_sha256": curated_hash,
        "manifest_sha256": expected_hash,
        "passed": passed,
    }


def _curation_integrity_check(spec: dict[str, Any]) -> dict[str, Any]:
    contract = spec["curation_contract"]
    manifest_path = PROJECT_ROOT / str(contract["manifest"])
    visual_path = PROJECT_ROOT / str(contract["visual_manifest"])
    if not manifest_path.is_file() or not visual_path.is_file():
        return _check("curated_asset_integrity", False, "Curation manifests are missing.", manifest_exists=manifest_path.is_file(), visual_manifest_exists=visual_path.is_file())

    manifest = _read_json(manifest_path)
    visual = _read_json(visual_path)
    figure_rows = [_asset_integrity(PROJECT_ROOT / item["source"], PROJECT_ROOT / item["curated"], str(item["curated_sha256"])) for item in manifest.get("figures", [])]
    media_rows: list[dict[str, Any]] = []
    for item in manifest.get("media", []):
        for kind in ("gif", "mp4"):
            asset = item.get(kind, {})
            media_rows.append(_asset_integrity(PROJECT_ROOT / asset["source"], PROJECT_ROOT / asset["curated"], str(asset["curated_sha256"])))

    claims = manifest.get("claim_classes", {})
    required_claims = {str(item) for item in contract["required_claim_classes"]}
    actual_claims = {str(key) for key, value in claims.items() if int(value) > 0}
    counts_ok = (
        int(manifest.get("figure_count", -1)) == int(contract["required_figures"])
        and int(manifest.get("media_pair_count", -1)) == int(contract["required_gif_mp4_pairs"])
        and len(figure_rows) == int(contract["required_figures"])
        and len(media_rows) == 2 * int(contract["required_gif_mp4_pairs"])
    )
    visual_booleans = {
        key: value for key, value in visual.items() if key.startswith("all_") and isinstance(value, bool)
    }
    visual_ok = str(visual.get("status")) == "PASS" and all(visual_booleans.values()) and not bool(visual.get("visible_phase_or_patch_labels", True)) and not bool(visual.get("legacy_assets_selected", True))
    passed = (
        str(manifest.get("status")) == "PASS"
        and counts_ok
        and required_claims.issubset(actual_claims)
        and all(item["passed"] for item in figure_rows)
        and all(item["passed"] for item in media_rows)
        and visual_ok
    )
    return _check(
        "curated_asset_integrity",
        passed,
        "Curated figures and media must hash-match their verified reference sources and preserve explicit limitation classes.",
        figure_rows=figure_rows,
        media_rows=media_rows,
        counts_ok=counts_ok,
        required_claim_classes=sorted(required_claims),
        actual_claim_classes=sorted(actual_claims),
        visual_quality=visual,
    )


def _premature_delivery_check(spec: dict[str, Any]) -> dict[str, Any]:
    controls = spec["release_controls"]
    word_files = sorted(path for path in DIRECTORIES["outputs"].rglob("*.docx") if path.is_file())
    zip_files = sorted(path for path in DIRECTORIES["deliverables"].rglob("*.zip") if path.is_file())
    expected_disabled = bool(controls.get("final_scripts_must_remain_disabled", True))
    passed = (not word_files if controls.get("word_report_must_not_exist", True) else True) and (not zip_files if controls.get("delivery_zip_must_not_exist", True) else True) and expected_disabled
    return _check(
        "no_premature_word_or_delivery_package",
        passed,
        "Word and delivery ZIP artifacts must remain absent while this gate produces only a release-candidate record.",
        word_files=[relative_to_root(path) for path in word_files],
        delivery_zip_files=[relative_to_root(path) for path in zip_files],
        final_scripts_must_remain_disabled=expected_disabled,
    )


def _record_gate_artifacts(report: dict[str, Any]) -> Path:
    run_id = "phase10_17_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = DIRECTORIES["phase10_17_runs"] / run_id
    inputs = run_dir / "inputs"
    artifacts = run_dir / "artifacts"
    inputs.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    config = DIRECTORIES["config"] / "reference_release_gate.yaml"
    shutil.copy2(config, inputs / config.name)
    copied: list[dict[str, Any]] = []
    for source in (GATE_JSON, GATE_MARKDOWN, GATE_TABLE):
        target = artifacts / source.name
        shutil.copy2(source, target)
        copied.append({"source": relative_to_root(source), "sha256": _sha256(source), "size_bytes": source.stat().st_size})
    manifest = {
        "identifier": "AQUASKIM-REL-GATE-REC-01",
        "run_id": run_id,
        "status": report["status"],
        "candidate_state": report["candidate_state"],
        "artifacts": copied,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    handoff = DIRECTORIES["handoffs"] / "PHASE10_17_LATEST_HANDOFF.md"
    handoff.write_text(
        "# Engineering Release Gate\n\n"
        f"- Run: `{run_id}`\n"
        f"- Status: `{report['status']}`\n"
        f"- Candidate state: `{report['candidate_state']}`\n"
        "- This record does not enable Word generation, a delivery ZIP or final release scripts.\n"
        f"- Evidence: `{relative_to_root(run_dir)}`\n",
        encoding="utf-8",
    )
    return run_dir


def build_release_gate_report() -> dict[str, Any]:
    """Run all non-simulation release-candidate audits and return a structured report."""
    ensure_runtime_directories()
    spec = load_release_gate_spec()
    checks = [
        *_upstream_integrity_checks(),
        _canonical_version_check(),
        _reference_policy_check(),
        _required_evidence_check(spec),
        _curation_integrity_check(spec),
        _premature_delivery_check(spec),
    ]
    passed = all(bool(check["passed"]) for check in checks)
    return {
        "identifier": str(spec["identifier"]),
        "title": str(spec["title"]),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Engineering release-candidate audit only; no mission render, Word report, delivery ZIP or release build.",
        "model_boundary": str(spec["model_boundary"]),
        "checks": checks,
        "status": "PASS" if passed else "FAIL",
        "candidate_state": "ENGINEERING_RELEASE_CANDIDATE" if passed else "NOT_RELEASE_READY",
        "final_release_enabled": False,
    }


def _write_csv(report: dict[str, Any]) -> None:
    rows: list[dict[str, str]] = []
    for item in report["checks"]:
        rows.append({
            "check": str(item["name"]),
            "status": "PASS" if item["passed"] else "FAIL",
            "detail": str(item["detail"]),
        })
    with GATE_TABLE.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["check", "status", "detail"])
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(report: dict[str, Any]) -> None:
    lines = [
        "# Engineering Release Gate",
        "",
        f"- Timestamp (UTC): `{report['timestamp_utc']}`",
        f"- Gate status: `{report['status']}`",
        f"- Candidate state: `{report['candidate_state']}`",
        "- Final release scripts: `DISABLED`",
        "- Explicitly not run: mission simulation, GIF/MP4 rendering, Word report, delivery ZIP, release build.",
        "",
        "## Gate checks",
    ]
    for check in report["checks"]:
        lines.append(f"- **{check['name']}**: `{'PASS' if check['passed'] else 'FAIL'}` — {check['detail']}")
    lines.extend([
        "",
        "## Interpretation",
        "A PASS is an internal engineering release-candidate result. It permits controlled Word-report construction in the next phase only; it does not create or authorize a delivery ZIP, distribution, certification or sea-trial claim.",
        "",
        "## Model boundary",
        str(report["model_boundary"]),
    ])
    GATE_MARKDOWN.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_release_gate_report(report: dict[str, Any], *, record: bool = True) -> Path | None:
    GATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    GATE_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(report)
    _write_markdown(report)
    return _record_gate_artifacts(report) if record else None


def run_release_gate(*, record: bool = True) -> tuple[dict[str, Any], Path | None]:
    report = build_release_gate_report()
    run_dir = write_release_gate_report(report, record=record)
    return report, run_dir


def print_release_gate_summary(report: dict[str, Any], run_dir: Path | None) -> None:
    print("=" * 72)
    print("AquaSkim-Sim | Engineering Release Gate")
    print("=" * 72)
    for check in report["checks"]:
        print(f"[{'OK' if check['passed'] else 'FAIL'}] {check['name']}")
    print(f"Report   : {relative_to_root(GATE_MARKDOWN)}")
    print(f"Manifest : {relative_to_root(GATE_JSON)}")
    print(f"Evidence : {relative_to_root(run_dir) if run_dir else 'not recorded'}")
    print(f"Status   : {report['status']}")
    print(f"Candidate: {report['candidate_state']}")
    print("Release  : DISABLED (Word and delivery ZIP remain blocked)")
    print("=" * 72)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AquaSkim-Sim engineering release-candidate gate")
    parser.add_argument("command", nargs="?", choices=("check", "report"), default="report")
    parser.add_argument("--no-record", action="store_true", help="Do not create a phase record.")
    args = parser.parse_args(argv)
    report, run_dir = run_release_gate(record=not args.no_record)
    print_release_gate_summary(report, run_dir)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
