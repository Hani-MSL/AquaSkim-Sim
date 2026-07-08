"""Read-only quality checks for retained historical Phase 08 artefacts."""
import json

from aquaskim.paths import DIRECTORIES


def test_phase08_visual_quality_manifest_is_readable_when_retained() -> None:
    manifest_path = DIRECTORIES["logs"] / "phase08_visual_quality_manifest.json"
    if not manifest_path.exists():
        return
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert len(manifest["exports"]) == 5
    for export in manifest["exports"]:
        assert export["width_px"] >= 3000
        assert export["height_px"] >= 1800
