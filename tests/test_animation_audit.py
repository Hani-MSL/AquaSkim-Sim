from __future__ import annotations

from pathlib import Path

from PIL import Image

from aquaskim.animation_audit import write_animation_audit_sheet


def test_animation_audit_sheet_samples_more_than_the_first_frame(tmp_path: Path) -> None:
    frames = [Image.new("RGB", (24, 16), color) for color in ("red", "green", "blue", "yellow", "black")]
    gif = tmp_path / "tiny.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=20, loop=0)
    output = tmp_path / "audit.png"
    write_animation_audit_sheet([gif], output)
    assert output.exists()
    assert Image.open(output).size[0] > 1000
