from __future__ import annotations

"""Final delivery package builder for Patch 10.19.

This module packages the already validated Word report and curated evidence into
an auditable ZIP. It intentionally does not run new simulations or create a
certification/release-build claim.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import zipfile
from typing import Any, Iterable

from aquaskim import __version__
from aquaskim.paths import DIRECTORIES, PROJECT_ROOT, ensure_runtime_directories, relative_to_root
from aquaskim.reference_design import load_reference_configuration

DELIVERY_IDENTIFIER = "AQUASKIM-FINAL-DELIVERY-01"
PACKAGE_BASENAME = f"AquaSkim-Sim_Final_Delivery_v{__version__}"

REQUIRED_REPRODUCTION_SCRIPTS = [
    "scripts/run_patch_10_11_reference_fidelity.bat",
    "scripts/run_patch_10_12_operating_envelope.bat",
    "scripts/run_patch_10_13_control_robustness.bat",
    "scripts/run_patch_10_13_1_control_hotfix.bat",
    "scripts/run_patch_10_14_payload_maneuver_validation.bat",
    "scripts/run_patch_10_15_system_scenario_validation.bat",
    "scripts/run_patch_10_16_presentation_curation.bat",
    "scripts/run_patch_10_17_engineering_release_gate.bat",
    "scripts/run_patch_10_18_final_word_report.bat",
    "scripts/run_patch_10_19_independent_rebuild_and_delivery.bat",
    "scripts/run_from_zero_to_delivery.bat",
]


class FinalDeliveryError(RuntimeError):
    """Raised when final delivery packaging cannot be certified."""


@dataclass(frozen=True)
class DeliveryFile:
    source: Path
    archive_path: str
    role: str
    required: bool = True


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:  # pragma: no cover - defensive clarity
        raise FinalDeliveryError(f"Required JSON is missing: {relative_to_root(path)}") from exc
    except json.JSONDecodeError as exc:
        raise FinalDeliveryError(f"Required JSON is invalid: {relative_to_root(path)}") from exc


def _required(path: Path, detail: str) -> Path:
    if not path.exists() or path.stat().st_size == 0:
        raise FinalDeliveryError(f"Missing required {detail}: {relative_to_root(path)}")
    return path


def _iter_existing(patterns: Iterable[str], *, base: Path = PROJECT_ROOT) -> list[Path]:
    files: list[Path] = []
    for pattern in patterns:
        files.extend(sorted(base.glob(pattern)))
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in files:
        if path.is_file() and path not in seen:
            seen.add(path)
            unique.append(path)
    return unique


def _is_excluded(path: Path) -> bool:
    rel = relative_to_root(path)
    parts = Path(rel).parts
    if any(part in {"__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache"} for part in parts):
        return True
    if rel.startswith("outputs/deliverables/"):
        return True
    if rel.endswith(".pyc") or rel.endswith(".pyo"):
        return True
    if rel.startswith("config/user_profile.yaml"):
        return True
    if "backup" in path.name.lower():
        return True
    if path.suffix.lower() == ".zip" and rel.startswith("outputs/"):
        return True
    return False


def _validate_prerequisites() -> dict[str, Any]:
    report = _required(DIRECTORIES["reports"] / "AquaSkim-Sim_Final_Report.docx", "final Word report")
    word_qa = _load_json(_required(DIRECTORIES["logs"] / "final_word_report_qa.json", "Word QA JSON"))
    word_manifest = _load_json(_required(DIRECTORIES["reports"] / "phase10_report_build_manifest.json", "Word build manifest"))
    release_gate = _load_json(_required(DIRECTORIES["logs"] / "engineering_release_gate.json", "engineering release gate JSON"))
    curation_manifest = _load_json(_required(DIRECTORIES["logs"] / "reference_presentation_visual_quality_manifest.json", "presentation visual QA JSON"))

    config = load_reference_configuration()
    version_checks = {
        "package": __version__,
        "reference_design": config.project_version,
        "word_manifest_report_sha_matches_docx": word_manifest.get("report_sha256") == _sha256(report),
        "word_qa_sha_matches_docx": word_qa.get("inspection", {}).get("sha256") == _sha256(report),
    }
    checks = {
        "word_qa_pass": word_qa.get("validation_status") == "PASS",
        "word_table_count_ge_8": int(word_qa.get("inspection", {}).get("table_count", 0)) >= 8,
        "word_media_count_ge_25": int(word_qa.get("inspection", {}).get("media_count", 0)) >= 25,
        "release_gate_pass": release_gate.get("status") == "PASS",
        "engineering_candidate": release_gate.get("candidate_state") == "ENGINEERING_RELEASE_CANDIDATE",
        "release_not_enabled_by_gate": release_gate.get("final_release_enabled") is False,
        "presentation_qa_pass": curation_manifest.get("status") == "PASS",
        "curated_figures_ge_14": int(curation_manifest.get("selected_figures", 0)) >= 14,
        "curated_media_ge_12_pairs": int(curation_manifest.get("selected_gifs", 0)) >= 12 and int(curation_manifest.get("selected_mp4s", 0)) >= 12,
        "versions_match": __version__ == config.project_version,
        "manifest_hashes_match_docx": bool(version_checks["word_manifest_report_sha_matches_docx"] and version_checks["word_qa_sha_matches_docx"]),
    }
    if not all(checks.values()):
        failing = {k: v for k, v in checks.items() if not v}
        raise FinalDeliveryError(f"Final delivery prerequisites failed: {json.dumps(failing, ensure_ascii=False)}")
    return {
        "checks": checks,
        "versions": version_checks,
        "report_sha256": _sha256(report),
        "word_qa": word_qa,
        "word_manifest": word_manifest,
        "release_gate": release_gate,
        "curation_manifest": curation_manifest,
    }


def _validate_reproduction_script_set() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    missing_or_empty: list[str] = []
    for relative in REQUIRED_REPRODUCTION_SCRIPTS:
        path = PROJECT_ROOT / relative
        exists = path.exists()
        size = path.stat().st_size if exists else 0
        row = {"path": relative, "exists": exists, "size_bytes": size, "sha256": _sha256(path) if exists and size > 0 else ""}
        rows.append(row)
        if not exists or size <= 0:
            missing_or_empty.append(relative)
    if missing_or_empty:
        raise FinalDeliveryError(
            "Required reproduction scripts are missing or empty before delivery packaging: "
            + json.dumps(missing_or_empty, ensure_ascii=False)
        )
    return rows




def preflight_reproduction_scripts() -> list[dict[str, Any]]:
    """Validate required reproduction scripts without assembling a delivery ZIP."""
    rows = _validate_reproduction_script_set()
    print("[OK] Reproduction scripts present and non-empty:")
    for row in rows:
        print(f"[OK] {row['path']} ({row['size_bytes']} bytes)")
    return rows


def _delivery_files() -> list[DeliveryFile]:
    files: list[DeliveryFile] = []
    add = files.append

    # Top-level readable artifacts.
    add(DeliveryFile(DIRECTORIES["reports"] / "AquaSkim-Sim_Final_Report.docx", "AquaSkim-Sim_Final_Report.docx", "final_report"))
    add(DeliveryFile(PROJECT_ROOT / "README.md", "README.md", "project_readme"))
    add(DeliveryFile(PROJECT_ROOT / "README_FA.md", "README_FA.md", "project_readme"))
    for name in ["pyproject.toml", "environment.yml"]:
        path = PROJECT_ROOT / name
        if path.exists():
            add(DeliveryFile(path, name, "reproduction_metadata"))

    # Source, configuration, scripts, tests and documentation.
    for relative in REQUIRED_REPRODUCTION_SCRIPTS:
        add(DeliveryFile(PROJECT_ROOT / relative, relative, "source_and_reproducibility"))

    source_patterns = [
        "src/aquaskim/**/*.py",
        "config/**/*.yaml",
        "config/report_metadata.json",
        "config/report_metadata.template.json",
        "scripts/*.bat",
        "tests/*.py",
        "docs/**/*.md",
        "PATCH_10_*_APPLY.md",
    ]
    for path in _iter_existing(source_patterns):
        if not _is_excluded(path):
            add(DeliveryFile(path, relative_to_root(path), "source_and_reproducibility"))

    # Reports and machine-readable audit outputs.
    output_patterns = [
        "outputs/reports/*.md",
        "outputs/reports/*.json",
        "outputs/logs/*.json",
        "outputs/tables/reference_*.csv",
        "outputs/figures/reference_presentation_evidence_overview.png",
        "outputs/presentation_evidence/**/*.png",
        "outputs/presentation_evidence/**/*.gif",
        "outputs/presentation_evidence/**/*.mp4",
    ]
    for path in _iter_existing(output_patterns):
        if not _is_excluded(path):
            add(DeliveryFile(path, relative_to_root(path), "validated_evidence"))

    # Handoffs and the final evidence records are small but valuable for audit.
    record_patterns = [
        "records/handoffs/PHASE10_*.md",
        "records/phases/phase_10_17/runs/**/*.json",
        "records/phases/phase_10_17/runs/**/*.md",
        "records/phases/phase_10_18/runs/**/*.json",
        "records/phases/phase_10_18/runs/**/*.md",
    ]
    for path in _iter_existing(record_patterns):
        if not _is_excluded(path):
            add(DeliveryFile(path, relative_to_root(path), "audit_record"))

    # Deduplicate by archive path, keeping the first role assignment.
    seen: set[str] = set()
    unique: list[DeliveryFile] = []
    for item in files:
        if item.archive_path not in seen:
            seen.add(item.archive_path)
            unique.append(item)
    return unique


def _clean_previous_delivery_outputs() -> None:
    deliverables = DIRECTORIES["deliverables"]
    deliverables.mkdir(parents=True, exist_ok=True)
    for pattern in (
        "AquaSkim-Sim_Final_Delivery_v*.zip",
        "FINAL_DELIVERY_PACKAGE_MANIFEST.json",
        "FINAL_DELIVERY_SHA256SUMS.txt",
        "final_delivery_package_audit.md",
    ):
        for path in deliverables.glob(pattern):
            try:
                path.unlink()
            except OSError as exc:
                raise FinalDeliveryError(f"Cannot remove stale delivery artifact; close viewers and retry: {relative_to_root(path)}") from exc


def build_final_delivery_package(*, record: bool = True) -> dict[str, Any]:
    ensure_runtime_directories()
    prerequisites = _validate_prerequisites()
    reproduction_script_rows = _validate_reproduction_script_set()
    _clean_previous_delivery_outputs()

    deliverables = DIRECTORIES["deliverables"]
    package_zip = deliverables / f"{PACKAGE_BASENAME}.zip"
    external_manifest_path = deliverables / "FINAL_DELIVERY_PACKAGE_MANIFEST.json"
    sums_path = deliverables / "FINAL_DELIVERY_SHA256SUMS.txt"
    audit_md_path = deliverables / "final_delivery_package_audit.md"

    files = _delivery_files()
    required_archive_paths = {
        "AquaSkim-Sim_Final_Report.docx",
        "README_FA.md",
        "pyproject.toml",
        "outputs/reports/phase10_report_build_manifest.json",
        "outputs/logs/final_word_report_qa.json",
        "outputs/logs/engineering_release_gate.json",
        "outputs/logs/reference_presentation_visual_quality_manifest.json",
    }
    archive_paths = {item.archive_path for item in files}
    missing = sorted(required_archive_paths - archive_paths)
    if missing:
        raise FinalDeliveryError(f"Required package entries missing from delivery set: {missing}")

    file_rows: list[dict[str, Any]] = []
    for item in files:
        if item.required:
            _required(item.source, item.role)
        file_rows.append({
            "path": item.archive_path,
            "source": relative_to_root(item.source),
            "role": item.role,
            "size_bytes": item.source.stat().st_size,
            "sha256": _sha256(item.source),
        })

    internal_manifest = {
        "identifier": DELIVERY_IDENTIFIER,
        "package_basename": PACKAGE_BASENAME,
        "project_version": __version__,
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "Final course-project delivery package assembled from the engineering-release-candidate Word report and curated reference evidence.",
        "model_boundary": "Numerical low-speed 3-DOF sheltered-basin evidence only; not sea-trial footage, certification, wave-response evidence or onboard current-estimation proof.",
        "final_report_sha256": prerequisites["report_sha256"],
        "prerequisite_checks": prerequisites["checks"],
        "required_reproduction_scripts": reproduction_script_rows,
        "explicit_non_claims": [
            "No sea-trial certification",
            "No wave-response validation",
            "No onboard current-estimator validation",
            "No hardware commissioning claim",
        ],
        "files": file_rows,
    }

    # Add the internal manifest/readme to the package via temporary files.
    temp_manifest = deliverables / "_DELIVERY_MANIFEST_IN_PACKAGE.json"
    temp_readme = deliverables / "_DELIVERY_README_IN_PACKAGE.md"
    temp_manifest.write_text(json.dumps(internal_manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temp_readme.write_text(
        "# AquaSkim-Sim final delivery package\n\n"
        f"- Project version: `{__version__}`\n"
        f"- Final report: `AquaSkim-Sim_Final_Report.docx`\n"
        "- Evidence source: curated fixed-reference outputs after Engineering Release Gate.\n"
        "- Boundary: low-speed 3-DOF sheltered-basin numerical model only.\n"
        "- This package does not claim sea-trial validation, wave-response validation or certification.\n",
        encoding="utf-8",
    )

    try:
        with zipfile.ZipFile(package_zip, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            archive.write(temp_manifest, "DELIVERY_MANIFEST.json")
            archive.write(temp_readme, "DELIVERY_README.md")
            for item in files:
                archive.write(item.source, item.archive_path)
    finally:
        temp_manifest.unlink(missing_ok=True)
        temp_readme.unlink(missing_ok=True)

    zip_sha = _sha256(package_zip)
    zip_size = package_zip.stat().st_size
    verification = _verify_package(package_zip, file_rows)
    if not verification["passed"]:
        raise FinalDeliveryError(f"Delivery ZIP verification failed: {json.dumps(verification, ensure_ascii=False)}")

    external_manifest = {
        **internal_manifest,
        "package_zip": relative_to_root(package_zip),
        "package_sha256": zip_sha,
        "package_size_bytes": zip_size,
        "zip_verification": verification,
        "release_status": "DELIVERY_PACKAGE_READY",
    }
    external_manifest_path.write_text(json.dumps(external_manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    sums_lines = [f"{zip_sha}  {package_zip.name}"]
    for row in file_rows:
        sums_lines.append(f"{row['sha256']}  {row['path']}")
    sums_path.write_text("\n".join(sums_lines) + "\n", encoding="utf-8")

    audit_md = _audit_markdown(external_manifest)
    audit_md_path.write_text(audit_md, encoding="utf-8")

    if record:
        _record_run(external_manifest, audit_md)

    return {
        "package_zip": relative_to_root(package_zip),
        "package_sha256": zip_sha,
        "package_size_bytes": zip_size,
        "manifest": relative_to_root(external_manifest_path),
        "sha256sums": relative_to_root(sums_path),
        "audit_report": relative_to_root(audit_md_path),
        "file_count": len(file_rows),
        "status": "PASS",
        "release_status": "DELIVERY_PACKAGE_READY",
    }


def _verify_package(package_zip: Path, file_rows: list[dict[str, Any]]) -> dict[str, Any]:
    expected = {row["path"]: row["sha256"] for row in file_rows}
    with zipfile.ZipFile(package_zip) as archive:
        names = set(archive.namelist())
        has_internal_manifest = "DELIVERY_MANIFEST.json" in names
        has_readme = "DELIVERY_README.md" in names
        mismatches = []
        for path, sha in expected.items():
            if path not in names:
                mismatches.append({"path": path, "issue": "missing"})
                continue
            digest = hashlib.sha256(archive.read(path)).hexdigest()
            if digest != sha:
                mismatches.append({"path": path, "issue": "sha256_mismatch", "expected": sha, "actual": digest})
        forbidden = [name for name in names if "backup" in Path(name).name.lower() or name.endswith(".pyc") or "__pycache__" in name]
    checks = {
        "zip_exists": package_zip.exists(),
        "zip_size_gt_5mb": package_zip.stat().st_size > 5_000_000,
        "has_internal_manifest": has_internal_manifest,
        "has_delivery_readme": has_readme,
        "all_listed_files_present_and_hash_match": not mismatches,
        "no_forbidden_files": not forbidden,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "mismatches": mismatches,
        "forbidden_entries": forbidden,
        "archive_file_count": len(names),
    }


def _audit_markdown(manifest: dict[str, Any]) -> str:
    checks = manifest["zip_verification"]["checks"]
    lines = [
        "# Final Delivery Package Audit",
        "",
        f"- Timestamp (UTC): `{manifest['created_utc']}`",
        f"- Status: `{manifest['release_status']}`",
        f"- Project version: `{manifest['project_version']}`",
        f"- Package: `{manifest['package_zip']}`",
        f"- Package SHA-256: `{manifest['package_sha256']}`",
        f"- Files listed: `{len(manifest['files'])}`",
        "",
        "## Verification checks",
    ]
    for name, value in checks.items():
        lines.append(f"- **{name}**: `{value}`")
    lines.extend([
        "",
        "## Scope",
        manifest["scope"],
        "",
        "## Model boundary",
        manifest["model_boundary"],
        "",
        "## Explicit non-claims",
    ])
    for claim in manifest["explicit_non_claims"]:
        lines.append(f"- {claim}")
    return "\n".join(lines) + "\n"


def _record_run(manifest: dict[str, Any], audit_md: str) -> None:
    run_id = "phase10_19_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    runs = DIRECTORIES["phase10_19_runs"]
    run_dir = runs / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "FINAL_DELIVERY_PACKAGE_MANIFEST.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_dir / "final_delivery_package_audit.md").write_text(audit_md, encoding="utf-8")
    handoff = DIRECTORIES["handoffs"] / "PHASE10_19_LATEST_HANDOFF.md"
    handoff.write_text(
        "# Final Delivery Package\n\n"
        f"- Run: `{run_id}`\n"
        "- Status: `PASS`\n"
        f"- Package: `{manifest['package_zip']}`\n"
        f"- Package SHA-256: `{manifest['package_sha256']}`\n"
        "- Release status: `DELIVERY_PACKAGE_READY`\n"
        "- This is a course-project delivery package, not a sea-trial or certification package.\n"
        f"- Evidence: `{relative_to_root(run_dir)}`\n",
        encoding="utf-8",
    )


def print_delivery_summary(result: dict[str, Any]) -> None:
    print("========================================================================")
    print("AquaSkim-Sim | Final Delivery Package")
    print("========================================================================")
    print(f"Package : {result['package_zip']}")
    print(f"SHA-256 : {result['package_sha256']}")
    print(f"Manifest: {result['manifest']}")
    print(f"SHA file: {result['sha256sums']}")
    print(f"Audit   : {result['audit_report']}")
    print(f"Files   : {result['file_count']}")
    print(f"Status  : {result['status']}")
    print(f"Release : {result['release_status']}")
    print("========================================================================")


if __name__ == "__main__":  # pragma: no cover
    if "--preflight-scripts" in sys.argv[1:]:
        preflight_reproduction_scripts()
    else:
        print_delivery_summary(build_final_delivery_package(record=True))
