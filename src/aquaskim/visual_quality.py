"""Reusable visual-quality utilities for AquaSkim-Sim engineering figures.

The project deliberately exports high-resolution PNG (for Word reports) and SVG
(for vector reuse).  Text-heavy labels are placed in dedicated information
panels instead of directly on geometry whenever possible.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
from PIL import Image


# Chosen for readability in print and on screen.  The final report can use
# Persian captions; technical drawings keep English component labels so that
# matplotlib font availability does not compromise the drawing.
PALETTE = {
    "navy": "#123047",
    "blue": "#2F6F9E",
    "sky": "#D9ECF7",
    "cyan": "#74B9D6",
    "orange": "#D9822B",
    "orange_light": "#F5D5B5",
    "green": "#2E7D5B",
    "green_light": "#CFEBDD",
    "gray_dark": "#39434D",
    "gray": "#6E7C87",
    "gray_light": "#E8EEF2",
    "grid": "#CBD5DC",
    "white": "#FFFFFF",
    "black": "#101820",
}


@dataclass(frozen=True)
class FigureExport:
    """Locations and raster dimensions for an exported engineering figure."""

    png_path: Path
    svg_path: Path
    width_px: int
    height_px: int

    def as_dict(self) -> dict[str, object]:
        return {
            "png": self.png_path.as_posix(),
            "svg": self.svg_path.as_posix(),
            "width_px": self.width_px,
            "height_px": self.height_px,
        }


def apply_engineering_style() -> None:
    """Apply a restrained, print-oriented Matplotlib style."""
    plt.rcParams.update(
        {
            "figure.facecolor": PALETTE["white"],
            "axes.facecolor": PALETTE["white"],
            "savefig.facecolor": PALETTE["white"],
            "font.family": "DejaVu Sans",
            "font.size": 10.0,
            "axes.titlesize": 15.0,
            "axes.titleweight": "bold",
            "axes.labelsize": 10.5,
            "axes.labelcolor": PALETTE["gray_dark"],
            "xtick.color": PALETTE["gray_dark"],
            "ytick.color": PALETTE["gray_dark"],
            "axes.edgecolor": PALETTE["gray_dark"],
            "axes.linewidth": 0.8,
            "grid.color": PALETTE["grid"],
            "grid.linestyle": ":",
            "grid.linewidth": 0.75,
            "legend.frameon": True,
            "legend.framealpha": 0.95,
            "legend.edgecolor": PALETTE["grid"],
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "svg.fonttype": "none",
        }
    )


def add_figure_header(
    figure: plt.Figure,
    title: str,
    subtitle: str,
    *,
    left: float = 0.055,
    title_y: float = 0.965,
    subtitle_y: float = 0.932,
) -> None:
    """Add a common report-quality title block outside the axes.

    Internal development phase labels are evidence metadata, not engineering
    content.  They are removed from the visible title so figures remain suitable
    for a report or a stand-alone technical presentation.
    """
    title = re.sub(r"\s*\|\s*Phase\s+\d+(?:\.\d+)?\s*[—-]?\s*", " | ", title, flags=re.IGNORECASE)
    subtitle = re.sub(r"\bPhase\s+\d+(?:\.\d+)?\b", "", subtitle, flags=re.IGNORECASE)
    figure.text(
        left,
        title_y,
        title,
        ha="left",
        va="top",
        fontsize=17,
        fontweight="bold",
        color=PALETTE["navy"],
    )
    figure.text(
        left,
        subtitle_y,
        subtitle,
        ha="left",
        va="top",
        fontsize=9.5,
        color=PALETTE["gray"],
    )
    figure.lines.append(
        plt.Line2D(
            [left, 0.95],
            [subtitle_y - 0.012, subtitle_y - 0.012],
            transform=figure.transFigure,
            color=PALETTE["cyan"],
            linewidth=1.0,
        )
    )


def style_axis(ax: plt.Axes, *, grid: bool = True) -> None:
    """Apply consistent axis styling."""
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    if grid:
        ax.grid(True, zorder=0)
    else:
        ax.grid(False)


def draw_number_badge(
    ax: plt.Axes,
    x: float,
    y: float,
    number: int,
    *,
    radius: float = 0.015,
    facecolor: str | None = None,
    textcolor: str | None = None,
    zorder: int = 8,
) -> None:
    """Draw a circular numbered callout marker."""
    from matplotlib.patches import Circle

    face = facecolor or PALETTE["navy"]
    txt = textcolor or PALETTE["white"]
    circle = Circle(
        (x, y),
        radius=radius,
        facecolor=face,
        edgecolor=PALETTE["white"],
        linewidth=1.2,
        zorder=zorder,
    )
    ax.add_patch(circle)
    ax.text(
        x,
        y,
        str(number),
        ha="center",
        va="center",
        color=txt,
        fontsize=8,
        fontweight="bold",
        zorder=zorder + 1,
    )


def add_dimension(
    ax: plt.Axes,
    start: tuple[float, float],
    end: tuple[float, float],
    text: str,
    *,
    text_offset: tuple[float, float] = (0.0, 0.0),
    color: str | None = None,
    fontsize: float = 8.5,
) -> None:
    """Draw an engineering dimension with a double-headed arrow."""
    draw_color = color or PALETTE["gray_dark"]
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "<->",
            "color": draw_color,
            "linewidth": 0.95,
            "shrinkA": 0,
            "shrinkB": 0,
        },
        zorder=6,
    )
    mid_x = (start[0] + end[0]) / 2.0 + text_offset[0]
    mid_y = (start[1] + end[1]) / 2.0 + text_offset[1]
    ax.text(
        mid_x,
        mid_y,
        text,
        ha="center",
        va="center",
        fontsize=fontsize,
        color=draw_color,
        bbox={
            "boxstyle": "round,pad=0.18",
            "facecolor": PALETTE["white"],
            "edgecolor": "none",
            "alpha": 0.92,
        },
        zorder=7,
    )


def export_figure(
    figure: plt.Figure,
    png_path: Path,
    *,
    dpi: int = 300,
    close: bool = True,
) -> FigureExport:
    """Export a print-quality PNG and matching vector SVG."""
    png_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path = png_path.with_suffix(".svg")
    figure.savefig(png_path, dpi=dpi, bbox_inches=None)
    figure.savefig(svg_path, format="svg", bbox_inches=None)

    with Image.open(png_path) as image:
        width_px, height_px = image.size

    if close:
        plt.close(figure)

    return FigureExport(
        png_path=png_path,
        svg_path=svg_path,
        width_px=width_px,
        height_px=height_px,
    )


def assert_export_quality(
    exports: Iterable[FigureExport],
    *,
    min_width_px: int = 3000,
    min_height_px: int = 1800,
) -> None:
    """Raise if an expected high-resolution output was not produced."""
    for export in exports:
        if not export.png_path.exists() or export.png_path.stat().st_size < 10_000:
            raise RuntimeError(f"PNG export is missing or unexpectedly small: {export.png_path}")
        if not export.svg_path.exists() or export.svg_path.stat().st_size < 1_000:
            raise RuntimeError(f"SVG export is missing or unexpectedly small: {export.svg_path}")
        if export.width_px < min_width_px or export.height_px < min_height_px:
            raise RuntimeError(
                "Figure resolution below project quality threshold: "
                f"{export.png_path.name} is {export.width_px}×{export.height_px}px; "
                f"minimum is {min_width_px}×{min_height_px}px."
            )
