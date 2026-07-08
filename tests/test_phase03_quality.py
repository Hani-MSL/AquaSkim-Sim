import json

import pytest
from PIL import Image

from aquaskim.phase03 import Phase03Artifacts, run_phase03


@pytest.fixture(scope="module")
def phase03_artifacts() -> Phase03Artifacts:
    """Generate Phase 03 once; all visual checks inspect this single run."""
    return run_phase03()


def test_phase03_generates_complete_report_artifacts(phase03_artifacts: Phase03Artifacts) -> None:
    for path in phase03_artifacts.__dict__.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_phase03_has_high_resolution_png_and_svg_exports(phase03_artifacts: Phase03Artifacts) -> None:
    raster_paths = [
        phase03_artifacts.hydrostatics_dashboard,
        phase03_artifacts.stability_curves,
        phase03_artifacts.heeling_cross_sections,
        phase03_artifacts.payload_envelope,
    ]
    for path in raster_paths:
        with Image.open(path) as image:
            width, height = image.size
        assert width >= 4500
        assert height >= 2400
        assert path.with_suffix(".svg").exists()

    manifest = json.loads(phase03_artifacts.visual_quality_manifest.read_text(encoding="utf-8"))
    assert manifest["quality_rule"]["minimum_png_width_px"] == 4500
    assert len(manifest["exports"]) == 4
