from PIL import Image

from aquaskim.phase02 import run_phase02


def test_phase02_generates_expected_artifacts() -> None:
    artifacts = run_phase02()
    for path in artifacts.__dict__.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_phase02_png_exports_meet_report_resolution_threshold() -> None:
    artifacts = run_phase02()
    for path in (
        artifacts.top_view,
        artifacts.side_view,
        artifacts.mass_distribution,
    ):
        with Image.open(path) as image:
            width_px, height_px = image.size
        assert width_px >= 3000
        assert height_px >= 1800


def test_phase02_vector_exports_exist() -> None:
    artifacts = run_phase02()
    for path in (
        artifacts.top_view_svg,
        artifacts.side_view_svg,
        artifacts.mass_distribution_svg,
    ):
        assert path.exists()
        assert path.stat().st_size > 1_000
