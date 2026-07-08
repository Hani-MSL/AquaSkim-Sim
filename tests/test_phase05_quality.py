from PIL import Image

from aquaskim.phase05 import run_phase05


def test_phase05_generates_complete_report_quality_artifacts() -> None:
    artifacts = run_phase05()
    paths = artifacts.__dict__
    for path in paths.values():
        assert path.exists()
        assert path.stat().st_size > 0

    for name in (
        "energy_dashboard",
        "mission_soc_profiles",
        "return_home_envelope",
        "energy_operating_envelope",
    ):
        png_path = paths[name]
        svg_path = paths[f"{name}_svg"]
        with Image.open(png_path) as image:
            width, height = image.size
        assert width >= 4500
        assert height >= 2400
        assert svg_path.exists()
        assert svg_path.stat().st_size > 1000
