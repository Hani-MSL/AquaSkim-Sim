"""Evidence-oriented contact sheets for animated engineering outputs."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable


def write_animation_audit_sheet(paths: Iterable[Path], output: Path, *, samples_per_animation: int = 5) -> None:
    """Create a multi-frame audit sheet rather than copying only GIF frame zero.

    The old contact sheets were visually misleading because they showed just the
    first frame of every GIF.  This sampler shows evenly spaced frames from each
    animation so reviewers can inspect motion progression without opening video.
    """
    from PIL import Image, ImageDraw

    valid = [Path(path) for path in paths if Path(path).exists()]
    if not valid:
        raise FileNotFoundError("No animation files were available for the audit sheet.")
    thumb_w, thumb_h = 286, 170
    left, top = 18, 30
    label_h, row_gap = 36, 28
    width = left * 2 + samples_per_animation * thumb_w
    height = top + len(valid) * (thumb_h + label_h + row_gap) + 14
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((left, 8), "Animation progress audit - evenly sampled frames", fill=(20, 45, 65))

    for row, path in enumerate(valid):
        image = Image.open(path)
        frame_count = max(1, int(getattr(image, "n_frames", 1)))
        indices = sorted({round(value * (frame_count - 1)) for value in [0.0, 0.25, 0.50, 0.75, 1.0]})
        if len(indices) < samples_per_animation:
            indices = [round(i * (frame_count - 1) / max(1, samples_per_animation - 1)) for i in range(samples_per_animation)]
        y = top + row * (thumb_h + label_h + row_gap)
        draw.text((left, y), path.stem, fill=(20, 45, 65))
        y += 16
        for column, frame_index in enumerate(indices[:samples_per_animation]):
            image.seek(int(frame_index))
            frame = image.convert("RGB")
            frame.thumbnail((thumb_w - 8, thumb_h - 8))
            x = left + column * thumb_w
            frame_x = x + (thumb_w - frame.width) // 2
            frame_y = y + (thumb_h - frame.height) // 2
            canvas.paste(frame, (frame_x, frame_y))
            draw.rectangle((x, y, x + thumb_w - 1, y + thumb_h - 1), outline=(190, 205, 215), width=1)
            percent = 0 if frame_count <= 1 else round(100 * frame_index / (frame_count - 1))
            draw.text((x + 4, y + thumb_h + 4), f"frame {frame_index + 1}/{frame_count}  |  {percent}%", fill=(70, 85, 95))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output)
