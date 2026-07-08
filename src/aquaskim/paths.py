"""Canonical project paths and directory contract.

All numerical, evidence and reporting modules must use these project-relative
locations. This source module is intentionally dependency-free so it can be
imported before configuration, simulation or evidence code.
"""
from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DIRECTORIES: dict[str, Path] = {
    "root": PROJECT_ROOT,
    "assets": PROJECT_ROOT / "assets",
    "cad": PROJECT_ROOT / "cad",
    "cad_generated": PROJECT_ROOT / "cad" / "generated",
    "config": PROJECT_ROOT / "config",
    "data": PROJECT_ROOT / "data",
    "data_raw": PROJECT_ROOT / "data" / "raw",
    "data_processed": PROJECT_ROOT / "data" / "processed",
    "data_generated": PROJECT_ROOT / "data" / "generated",
    "docs": PROJECT_ROOT / "docs",
    "outputs": PROJECT_ROOT / "outputs",
    "figures": PROJECT_ROOT / "outputs" / "figures",
    "animations": PROJECT_ROOT / "outputs" / "animations",
    "videos": PROJECT_ROOT / "outputs" / "videos",
    "logs": PROJECT_ROOT / "outputs" / "logs",
    "tables": PROJECT_ROOT / "outputs" / "tables",
    "cad_renders": PROJECT_ROOT / "outputs" / "cad_renders",
    "reports": PROJECT_ROOT / "outputs" / "reports",
    "deliverables": PROJECT_ROOT / "outputs" / "deliverables",
    "presentation_evidence": PROJECT_ROOT / "outputs" / "presentation_evidence",
    "report": PROJECT_ROOT / "report",
    "scripts": PROJECT_ROOT / "scripts",
    "tests": PROJECT_ROOT / "tests",
    "visuals": PROJECT_ROOT / "visuals",
    "records": PROJECT_ROOT / "records",
    "phase_records": PROJECT_ROOT / "records" / "phases",
    "handoffs": PROJECT_ROOT / "records" / "handoffs",
    "manifests": PROJECT_ROOT / "records" / "manifests",
    "bootstrap_logs": PROJECT_ROOT / "records" / "bootstrap",
    "build_records": PROJECT_ROOT / "records" / "builds",
    "builds": PROJECT_ROOT / "records" / "builds",
}

# Explicit aliases preserve compatibility with every existing evidence writer.
for suffix in (
    "01", "02", "03", "04", "05", "06", "07", "08", "09", "10",
    "08_1", "08_2", "09_2", "10_1", "10_2", "10_3", "10_4", "10_5", "10_6", "10_7", "10_8", "10_9", "10_11", "10_12", "10_13", "10_14", "10_15", "10_16", "10_17", "10_18", "10_19", "10_20", "11",
):
    logical = f"phase{suffix}"
    physical = f"phase_{suffix}"
    records = PROJECT_ROOT / "records" / "phases" / physical
    DIRECTORIES[f"{logical}_records"] = records
    DIRECTORIES[f"{logical}_runs"] = records / "runs"


def ensure_runtime_directories() -> None:
    """Create writable runtime folders without deleting previous artifacts."""
    non_writable_source_keys = {
        "root", "assets", "cad", "config", "docs", "report", "scripts",
        "tests", "visuals",
    }
    for key, directory in DIRECTORIES.items():
        if key not in non_writable_source_keys:
            directory.mkdir(parents=True, exist_ok=True)


def relative_to_root(path: Path) -> str:
    """Return a slash-normalized, portable project-relative path where possible."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return path.resolve().as_posix()
