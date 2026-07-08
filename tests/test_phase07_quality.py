import json

from aquaskim.phase07 import run_phase07


def test_phase07_generates_report_quality_artifacts() -> None:
    artifacts = run_phase07()
    for path in artifacts.__dict__.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_phase07_summary_and_quality_manifest_are_complete() -> None:
    artifacts = run_phase07()
    summary = json.loads(artifacts.summary_json.read_text(encoding="utf-8"))
    manifest = json.loads(artifacts.visual_quality_manifest.read_text(encoding="utf-8"))
    assert summary["environment"]["debris_count"] == 28
    assert summary["occupancy_grid"]["occupied_cells"] > 0
    assert len(manifest["exports"]) == 4
    assert all(item["width_px"] >= 3000 for item in manifest["exports"])
    assert all(item["height_px"] >= 1800 for item in manifest["exports"])
