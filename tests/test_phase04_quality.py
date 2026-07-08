import json

import pytest
from PIL import Image

from aquaskim.phase04 import Phase04Artifacts, run_phase04


@pytest.fixture(scope="module")
def phase04_artifacts() -> Phase04Artifacts:
    return run_phase04()


def test_phase04_generates_complete_artifacts(phase04_artifacts: Phase04Artifacts) -> None:
    for path in phase04_artifacts.__dict__.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_phase04_has_high_resolution_png_and_svg_exports(phase04_artifacts: Phase04Artifacts) -> None:
    rasters = [
        phase04_artifacts.resistance_dashboard,
        phase04_artifacts.propulsion_envelope,
        phase04_artifacts.current_penalty,
        phase04_artifacts.operating_envelope,
    ]
    for path in rasters:
        with Image.open(path) as image:
            width, height = image.size
        assert width >= 4500
        assert height >= 2400
        assert path.with_suffix(".svg").exists()
    manifest = json.loads(phase04_artifacts.visual_quality_manifest.read_text(encoding="utf-8"))
    assert manifest["quality_rule"]["minimum_png_width_px"] == 4500
    assert len(manifest["exports"]) == 4
