"""Final presentation-evidence curation for existing reference artifacts.

This phase does not execute a digital-twin mission and does not create a Word
report, delivery ZIP or release artifact. It only curates and verifies existing
fixed-reference figures and replays for later human review.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from aquaskim.presentation_curation import curate_presentation_evidence
from aquaskim.reference_design import project_root


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _record(result: dict[str, Any]) -> Path:
    root = project_root()
    run_id = "phase10_16_" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = root / "records" / "phases" / "phase_10_16" / "runs" / run_id
    input_dir = run_dir / "inputs"
    artifact_dir = run_dir / "artifacts"
    input_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    config = root / "config" / "reference_presentation_curation.yaml"
    shutil.copy2(config, input_dir / config.name)
    records: list[dict[str, Any]] = []
    for key in ("report", "inventory", "visual_qa", "overview", "figure_contact_sheet", "media_contact_sheet"):
        path = Path(result[key])
        copied = artifact_dir / path.name
        shutil.copy2(path, copied)
        records.append({"role": key, "source": path.relative_to(root).as_posix(), "sha256": _sha256(path), "size_bytes": path.stat().st_size})
    manifest = {"identifier": "AQUASKIM-REF-PRESENT-REC-01", "run_id": run_id, "status": "PASS", "artifacts": records}
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    handoff = root / "records" / "handoffs" / "PHASE10_16_LATEST_HANDOFF.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text(
        "# Presentation Evidence Curation\n\n"
        f"- Run: `{run_id}`\n"
        "- Status: `PASS`\n"
        f"- Curated figures: `{result['figure_count']}`\n"
        f"- Curated GIF / MP4 pairs: `{result['media_pair_count']} / {result['media_pair_count']}`\n"
        "- Policy: Reference-only assets; boundary and controlled-failure material remains explicitly labelled.\n"
        "- No Word report, delivery ZIP or release artifact was created.\n",
        encoding="utf-8",
    )
    return run_dir


def run_phase10_16(*, record: bool = True) -> tuple[dict[str, Any], Path | None]:
    result = curate_presentation_evidence()
    run_dir = _record(result) if record else None
    return result, run_dir


def print_phase10_16_summary(result: tuple[dict[str, Any], Path | None] | dict[str, Any]) -> None:
    payload, run_dir = result if isinstance(result, tuple) else (result, None)
    root = project_root()
    relative = lambda value: Path(value).relative_to(root).as_posix()
    print("=" * 72)
    print("AquaSkim-Sim | Final Presentation Evidence Curation")
    print("=" * 72)
    print(f"Curated figures : {payload['figure_count']}")
    print(f"Curated media   : {payload['media_pair_count']} GIF / {payload['media_pair_count']} MP4")
    print(f"Overview        : {relative(payload['overview'])}")
    print(f"Figure sheet    : {relative(payload['figure_contact_sheet'])}")
    print(f"Media sheet     : {relative(payload['media_contact_sheet'])}")
    print(f"Visual QA       : {relative(payload['visual_qa'])}")
    print(f"Evidence        : {relative(run_dir) if run_dir else 'not recorded'}")
    print("Status          : PASS")
    print("=" * 72)


if __name__ == "__main__":
    print_phase10_16_summary(run_phase10_16(record=True))
