"""Phase 02: parametric mechanical architecture and mass-property evidence.

This module is deliberately reconstructed from the current project source of
truth rather than from archived PNG files.  It consumes the shared mechanical
geometry and mass-budget configuration, computes dry/full load cases through
``mass_properties.py``, and recreates the original report-quality artifact
contract used by downstream hydrostatics and report modules.

Scope boundary
--------------
The draft/freeboard values generated here are *previews* based on a constant
waterplane-area approximation.  Formal hydrostatics, metacentric height and
righting-moment analysis remain Phase 03 responsibilities.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from textwrap import fill
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import FancyBboxPatch, Polygon, Rectangle
import numpy as np

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.geometry import CatamaranGeometry
from aquaskim.mass_properties import MassProperties, PointMass, build_load_cases, mass_rows
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.visual_quality import (
    PALETTE,
    FigureExport,
    add_dimension,
    add_figure_header,
    apply_engineering_style,
    assert_export_quality,
    draw_number_badge,
    export_figure,
    style_axis,
)


@dataclass(frozen=True)
class Phase02Artifacts:
    """Complete Phase 02 artifact inventory retained by downstream modules."""

    top_view: Path
    top_view_svg: Path
    side_view: Path
    side_view_svg: Path
    mass_distribution: Path
    mass_distribution_svg: Path
    geometry_table: Path
    mass_budget_table: Path
    mass_cases_table: Path
    component_key_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write an empty Phase 02 table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _case_row(name: str, properties: MassProperties, geometry: CatamaranGeometry) -> dict[str, object]:
    draft = geometry.draft_preview_m(properties.total_mass_kg)
    return {
        "load_case": name,
        "total_mass_kg": properties.total_mass_kg,
        "cg_x_m": properties.cg_m[0],
        "cg_y_m": properties.cg_m[1],
        "cg_z_m": properties.cg_m[2],
        "Ixx_kg_m2": properties.inertia_kg_m2[0],
        "Iyy_kg_m2": properties.inertia_kg_m2[1],
        "Izz_kg_m2": properties.inertia_kg_m2[2],
        "draft_preview_m": draft,
        "freeboard_preview_m": geometry.freeboard_preview_m(properties.total_mass_kg),
        "displacement_capacity_ratio": geometry.capacity_mass_kg / properties.total_mass_kg,
    }


def _panel(ax: plt.Axes, *, x: float = 0.03, y: float = 0.03, width: float = 0.94, height: float = 0.94) -> None:
    ax.set_axis_off()
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.add_patch(
        FancyBboxPatch(
            (x, y), width, height,
            boxstyle="round,pad=0.018,rounding_size=0.022",
            facecolor="#F8FBFD",
            edgecolor=PALETTE["grid"],
            linewidth=1.0,
        )
    )


def _panel_heading(ax: plt.Axes, title: str, subtitle: str | None = None) -> None:
    ax.text(0.08, 0.92, title, va="top", fontsize=12.0, fontweight="bold", color=PALETTE["navy"])
    if subtitle:
        ax.text(0.08, 0.86, fill(subtitle, width=51), va="top", fontsize=8.25, linespacing=1.35, color=PALETTE["gray"])


def _metric_table(ax: plt.Axes, rows: list[tuple[str, str]], *, top: float, row_h: float = 0.052) -> float:
    x0, label_w, value_w = 0.08, 0.52, 0.30
    y = top
    for index, (label, value) in enumerate(rows):
        face = PALETTE["gray_light"] if index % 2 == 0 else PALETTE["white"]
        ax.add_patch(Rectangle((x0, y - row_h), label_w, row_h, facecolor=face, edgecolor=PALETTE["grid"], linewidth=0.55))
        ax.add_patch(Rectangle((x0 + label_w, y - row_h), value_w, row_h, facecolor=PALETTE["white"], edgecolor=PALETTE["grid"], linewidth=0.55))
        ax.text(x0 + 0.012, y - row_h / 2.0, label, va="center", ha="left", fontsize=7.65, color=PALETTE["gray_dark"])
        ax.text(x0 + label_w + value_w / 2.0, y - row_h / 2.0, value, va="center", ha="center", fontsize=7.75, fontweight="bold", color=PALETTE["navy"])
        y -= row_h
    return y


def _bullet_list(ax: plt.Axes, title: str, bullets: list[str], *, y: float, width: int = 47) -> None:
    ax.text(0.08, y, title, va="top", fontsize=10.0, fontweight="bold", color=PALETTE["navy"])
    y -= 0.045
    for bullet in bullets:
        wrapped = fill(bullet, width=width)
        ax.text(0.095, y, "• " + wrapped.replace("\n", "\n  "), va="top", fontsize=8.05, linespacing=1.35, color=PALETTE["gray_dark"])
        y -= 0.034 * (wrapped.count("\n") + 1) + 0.018


def _component_key(components: list[PointMass]) -> list[dict[str, object]]:
    descriptions = {
        "hull_left": "Port buoyant hull",
        "hull_right": "Starboard buoyant hull",
        "crossbeams_and_deck": "Twin-hull structural bridge and deck",
        "battery": "Low-mounted energy pack",
        "thruster_left": "Port differential thruster",
        "thruster_right": "Starboard differential thruster",
        "electronics": "Controller, sensors and communication module",
        "collector": "Forward V-funnel collection guide",
        "basket": "Central removable debris hopper",
        "enclosure": "Weather-protected electronics enclosure",
        "wiring_and_fasteners": "Cables, fasteners and integration allowance",
    }
    rows: list[dict[str, object]] = []
    for index, component in enumerate(components, start=1):
        rows.append(
            {
                "callout": index,
                "component": component.name,
                "function": descriptions.get(component.name, "Configured point-mass subsystem"),
                "mass_kg": component.mass_kg,
                "x_m": component.position_m[0],
                "y_m": component.position_m[1],
                "z_m": component.position_m[2],
            }
        )
    return rows


def _draw_top_view(
    geometry: CatamaranGeometry,
    components: list[PointMass],
    path: Path,
) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 9.5))
    grid = GridSpec(1, 2, figure=fig, width_ratios=(1.7, 0.88), left=0.055, right=0.95, top=0.86, bottom=0.085, wspace=0.10)
    ax = fig.add_subplot(grid[0, 0])
    info = fig.add_subplot(grid[0, 1])
    add_figure_header(
        fig,
        "Parametric catamaran mechanical architecture",
        "Plan view: twin buoyant hulls, collector funnel, hopper, differential thrust and the configured mass locations.",
    )

    hull_x0 = -geometry.hull_length_m / 2.0
    for y_center in geometry.hull_centerlines_y_m():
        ax.add_patch(
            Rectangle(
                (hull_x0, y_center - geometry.hull_width_m / 2.0),
                geometry.hull_length_m,
                geometry.hull_width_m,
                facecolor=PALETTE["sky"],
                edgecolor=PALETTE["navy"],
                linewidth=1.8,
                zorder=2,
            )
        )
        ax.plot([hull_x0 + 0.05, hull_x0 + geometry.hull_length_m - 0.05], [y_center, y_center], color=PALETTE["cyan"], linewidth=1.0, zorder=3)

    outlet_x = geometry.hull_length_m * 0.29
    inlet_x = geometry.hull_length_m / 2.0 + geometry.collector_length_m
    funnel = Polygon(
        [
            (outlet_x, -geometry.collector_outlet_width_m / 2.0),
            (inlet_x, -geometry.collector_inlet_width_m / 2.0),
            (inlet_x, geometry.collector_inlet_width_m / 2.0),
            (outlet_x, geometry.collector_outlet_width_m / 2.0),
        ],
        closed=True,
        facecolor=PALETTE["orange_light"],
        edgecolor=PALETTE["orange"],
        linewidth=1.65,
        zorder=3,
    )
    ax.add_patch(funnel)
    basket = Rectangle((0.09, -0.065), 0.17, 0.13, facecolor=PALETTE["green_light"], edgecolor=PALETTE["green"], linewidth=1.45, zorder=4)
    ax.add_patch(basket)
    ax.text(0.175, 0.0, "HOPPER", ha="center", va="center", fontsize=7.5, fontweight="bold", color=PALETTE["green"], zorder=5)

    thruster_x = hull_x0 - 0.045
    for y_center in geometry.hull_centerlines_y_m():
        ax.add_patch(Rectangle((thruster_x, y_center - 0.025), 0.038, 0.05, facecolor=PALETTE["gray_dark"], edgecolor=PALETTE["black"], linewidth=0.9, zorder=4))
        ax.arrow(thruster_x - 0.01, y_center, -0.07, 0.0, width=0.003, head_width=0.022, head_length=0.020, color=PALETTE["blue"], length_includes_head=True, zorder=4)

    callout_positions = {
        "hull_left": (0.00, 0.18),
        "hull_right": (0.00, -0.18),
        "crossbeams_and_deck": (-0.10, 0.0),
        "battery": (-0.05, 0.0),
        "thruster_left": (thruster_x + 0.015, 0.18),
        "thruster_right": (thruster_x + 0.015, -0.18),
        "electronics": (0.04, 0.0),
        "collector": (0.45, 0.0),
        "basket": (0.175, 0.0),
        "enclosure": (-0.02, 0.0),
        "wiring_and_fasteners": (0.0, 0.0),
    }
    for number, component in enumerate(components, start=1):
        px, py = callout_positions.get(component.name, component.position_m[:2])
        draw_number_badge(ax, px, py, number, radius=0.017)

    ax.arrow(0.33, 0.29, 0.15, 0.0, width=0.003, head_width=0.020, head_length=0.024, color=PALETTE["green"], length_includes_head=True, zorder=5)
    ax.text(0.405, 0.315, "forward / collection direction", ha="center", va="bottom", fontsize=8.0, color=PALETTE["green"], fontweight="bold")
    add_dimension(ax, (hull_x0, -0.285), (geometry.hull_length_m / 2.0, -0.285), f"Hull length = {geometry.hull_length_m:.3f} m", text_offset=(0.0, -0.026))
    add_dimension(ax, (-0.48, -geometry.overall_width_m / 2.0), (-0.48, geometry.overall_width_m / 2.0), f"Overall width = {geometry.overall_width_m:.3f} m", text_offset=(-0.075, 0.0))
    add_dimension(ax, (inlet_x, -geometry.collector_inlet_width_m / 2.0), (inlet_x, geometry.collector_inlet_width_m / 2.0), f"Inlet = {geometry.collector_inlet_width_m:.3f} m", text_offset=(0.075, 0.0))
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-0.60, 0.70)
    ax.set_ylim(-0.36, 0.36)
    ax.set_xlabel("Longitudinal coordinate x [m]")
    ax.set_ylabel("Transverse coordinate y [m]")
    ax.set_title("Geometry and callout locations", loc="left", fontsize=12.0)
    style_axis(ax)

    _panel(info)
    _panel_heading(info, "CONFIGURED SUBSYSTEM KEY", "Numbered badges identify configured point-mass locations. Long labels are intentionally kept outside the geometry.")
    y = 0.77
    for number, component in enumerate(components, start=1):
        info.text(0.09, y, f"{number:02d}", color=PALETTE["white"], ha="center", va="center", fontsize=7.0, fontweight="bold", bbox={"boxstyle": "circle,pad=0.29", "facecolor": PALETTE["navy"], "edgecolor": PALETTE["white"]})
        label = component.name.replace("_", " ")
        info.text(0.15, y, label, fontsize=7.65, va="center", color=PALETTE["gray_dark"])
        info.text(0.89, y, f"{component.mass_kg:.2f} kg", fontsize=7.45, va="center", ha="right", color=PALETTE["gray"], fontweight="bold")
        y -= 0.048
    info.text(0.08, 0.16, "Design rule", fontsize=9.0, fontweight="bold", color=PALETTE["navy"])
    info.text(0.08, 0.115, fill("Battery and heavy propulsion components are located low and symmetrically where possible; the forward collector and hopper are tracked explicitly in the full-payload CG case.", 49), fontsize=7.65, va="top", linespacing=1.35, color=PALETTE["gray_dark"])

    return export_figure(fig, path, dpi=320)


def _draw_side_view(
    geometry: CatamaranGeometry,
    cases: dict[str, tuple[list[PointMass], MassProperties]],
    path: Path,
) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 8.8))
    grid = GridSpec(1, 2, figure=fig, width_ratios=(1.65, 0.92), left=0.055, right=0.95, top=0.86, bottom=0.09, wspace=0.10)
    ax = fig.add_subplot(grid[0, 0])
    info = fig.add_subplot(grid[0, 1])
    add_figure_header(
        fig,
        "Side-profile layout and preliminary draft preview",
        "The preview uses the shared effective-waterplane approximation; Phase 03 supplies the formal hydrostatic and stability analysis.",
    )

    dry_props = cases["dry_empty_basket"][1]
    full_props = cases["full_design_payload"][1]
    dry_draft = geometry.draft_preview_m(dry_props.total_mass_kg)
    full_draft = geometry.draft_preview_m(full_props.total_mass_kg)
    x0 = -geometry.hull_length_m / 2.0
    ax.add_patch(Rectangle((x0, 0.0), geometry.hull_length_m, geometry.hull_height_m, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], linewidth=1.9, zorder=2))
    ax.add_patch(Polygon([(geometry.hull_length_m / 2.0 - 0.02, 0.075), (geometry.hull_length_m / 2.0 + geometry.collector_length_m, 0.030), (geometry.hull_length_m / 2.0 + geometry.collector_length_m, 0.095)], closed=True, facecolor=PALETTE["orange_light"], edgecolor=PALETTE["orange"], linewidth=1.5, zorder=3))
    ax.add_patch(Rectangle((0.09, 0.07), 0.17, 0.075, facecolor=PALETTE["green_light"], edgecolor=PALETTE["green"], linewidth=1.4, zorder=4))
    ax.add_patch(Rectangle((-0.15, 0.105), 0.26, 0.07, facecolor=PALETTE["gray_light"], edgecolor=PALETTE["gray_dark"], linewidth=1.25, zorder=4))
    ax.add_patch(Rectangle((-0.11, 0.035), 0.13, 0.050, facecolor="#E7EEF5", edgecolor=PALETTE["blue"], linewidth=1.2, zorder=4))
    for x_thruster in (-0.37, -0.33):
        ax.add_patch(Rectangle((x_thruster, 0.04), 0.025, 0.060, facecolor=PALETTE["gray_dark"], edgecolor=PALETTE["black"], linewidth=0.8, zorder=4))

    ax.axhspan(0.0, dry_draft, color=PALETTE["sky"], alpha=0.22, zorder=1)
    ax.axhline(dry_draft, color=PALETTE["blue"], linewidth=1.6, label=f"dry preview waterline ({dry_draft:.3f} m)", zorder=5)
    ax.axhline(full_draft, color=PALETTE["orange"], linewidth=1.6, linestyle="--", label=f"full payload waterline ({full_draft:.3f} m)", zorder=5)
    for label, props, color in (("CG dry", dry_props, PALETTE["blue"]), ("CG full", full_props, PALETTE["orange"])):
        ax.plot(props.cg_m[0], props.cg_m[2], marker="o", markersize=8, color=color, zorder=6)
        ax.annotate(label, xy=(props.cg_m[0], props.cg_m[2]), xytext=(props.cg_m[0] + 0.06, props.cg_m[2] + 0.020), fontsize=8.1, color=color, arrowprops={"arrowstyle": "-", "color": color, "linewidth": 0.9})

    labels = [
        ("Collector guide", (0.42, 0.10)),
        ("Hopper", (0.175, 0.155)),
        ("Electronics enclosure", (-0.03, 0.205)),
        ("Low battery zone", (-0.08, 0.010)),
        ("Aft thruster", (-0.36, 0.120)),
    ]
    for text, point in labels:
        ax.annotate(text, xy=point, xytext=(point[0] + 0.02, point[1] + 0.055), fontsize=7.55, color=PALETTE["gray_dark"], arrowprops={"arrowstyle": "-", "color": PALETTE["gray"], "linewidth": 0.75})

    add_dimension(ax, (x0, -0.035), (geometry.hull_length_m / 2.0, -0.035), f"Hull length = {geometry.hull_length_m:.3f} m", text_offset=(0.0, -0.020))
    add_dimension(ax, (-0.46, 0.0), (-0.46, geometry.hull_height_m), f"Hull height = {geometry.hull_height_m:.3f} m", text_offset=(-0.085, 0.0))
    ax.set_xlim(-0.52, 0.66)
    ax.set_ylim(-0.08, 0.28)
    ax.set_xlabel("Longitudinal coordinate x [m]")
    ax.set_ylabel("Vertical coordinate z [m]")
    ax.set_title("Configured side layout and load-state waterlines", loc="left", fontsize=12.0)
    ax.legend(loc="upper left", fontsize=7.7)
    style_axis(ax)

    dry_free = geometry.freeboard_preview_m(dry_props.total_mass_kg)
    full_free = geometry.freeboard_preview_m(full_props.total_mass_kg)
    _panel(info)
    _panel_heading(info, "LOAD-STATE PREVIEW", "No claim of certified seaworthiness is made here. The same values are carried forward into the formal Phase 03 hydrostatics model.")
    y = _metric_table(
        info,
        [
            ("Dry mass", f"{dry_props.total_mass_kg:.3f} kg"),
            ("Full design mass", f"{full_props.total_mass_kg:.3f} kg"),
            ("Dry draft preview", f"{dry_draft:.4f} m"),
            ("Full draft preview", f"{full_draft:.4f} m"),
            ("Dry freeboard preview", f"{dry_free:.4f} m"),
            ("Full freeboard preview", f"{full_free:.4f} m"),
            ("Dry CG height", f"{dry_props.cg_m[2]:.4f} m"),
            ("Full CG height", f"{full_props.cg_m[2]:.4f} m"),
        ],
        top=0.77,
    )
    _bullet_list(
        info,
        "ENGINEERING INTERPRETATION",
        [
            "The deck bridge, electronics enclosure and collector remain above the preview waterlines in both design states.",
            "The payload shifts CG forward because the collection hopper is located ahead of midship; the shift is explicitly quantified in the mass-case table.",
            "The apparent freeboard margin is a first-pass geometry check only; heel and asymmetric loading are evaluated separately in Phase 03.",
        ],
        y=y - 0.045,
    )
    return export_figure(fig, path, dpi=320)


def _draw_mass_distribution(
    geometry: CatamaranGeometry,
    dry_components: list[PointMass],
    cases: dict[str, tuple[list[PointMass], MassProperties]],
    path: Path,
) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 10.0))
    grid = GridSpec(2, 2, figure=fig, width_ratios=(1.12, 0.88), height_ratios=(1.0, 0.87), left=0.055, right=0.95, top=0.86, bottom=0.08, hspace=0.38, wspace=0.25)
    ax_mass = fig.add_subplot(grid[0, 0])
    ax_layout = fig.add_subplot(grid[0, 1])
    ax_inertia = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[1, 1])
    add_figure_header(
        fig,
        "Mass budget, centre-of-gravity shift and conceptual inertia",
        "All values are regenerated from the versioned component mass budget; inertia is a transparent point-mass approximation about the computed CG.",
    )

    names = [component.name.replace("_", " ") for component in dry_components]
    masses = [component.mass_kg for component in dry_components]
    order = np.argsort(masses)
    ax_mass.barh(np.array(names)[order], np.array(masses)[order], color=PALETTE["blue"], zorder=3)
    ax_mass.set_xlabel("Component mass [kg]")
    ax_mass.set_title("Configured dry-mass budget", loc="left", fontsize=12.0)
    for value, y in zip(np.array(masses)[order], np.arange(len(order))):
        ax_mass.text(float(value) + 0.006, y, f"{float(value):.2f}", va="center", fontsize=7.6, color=PALETTE["gray_dark"])
    style_axis(ax_mass)

    for y_center in geometry.hull_centerlines_y_m():
        ax_layout.add_patch(Rectangle((-geometry.hull_length_m / 2.0, y_center - geometry.hull_width_m / 2.0), geometry.hull_length_m, geometry.hull_width_m, facecolor=PALETTE["sky"], edgecolor=PALETTE["navy"], linewidth=1.1, zorder=1))
    marker_styles = [("dry_empty_basket", "Dry CG", PALETTE["blue"], "o"), ("full_design_payload", "Full payload CG", PALETTE["orange"], "s")]
    for case_name, label, color, marker in marker_styles:
        props = cases[case_name][1]
        ax_layout.scatter([props.cg_m[0]], [props.cg_m[1]], marker=marker, s=100, color=color, edgecolor=PALETTE["white"], linewidth=1.0, label=label, zorder=5)
        ax_layout.annotate(f"({props.cg_m[0]:+.3f}, {props.cg_m[1]:+.3f}) m", xy=(props.cg_m[0], props.cg_m[1]), xytext=(props.cg_m[0] + 0.025, props.cg_m[1] + (0.055 if case_name == "dry_empty_basket" else -0.065)), fontsize=7.5, color=color, arrowprops={"arrowstyle": "-", "linewidth": 0.8, "color": color})
    ax_layout.set_aspect("equal", adjustable="box")
    ax_layout.set_xlim(-0.42, 0.42)
    ax_layout.set_ylim(-0.28, 0.28)
    ax_layout.set_xlabel("x [m]")
    ax_layout.set_ylabel("y [m]")
    ax_layout.set_title("CG location in the planform", loc="left", fontsize=12.0)
    ax_layout.legend(loc="upper right", fontsize=7.5)
    style_axis(ax_layout)

    inertias = ["Ixx", "Iyy", "Izz"]
    dry_i = cases["dry_empty_basket"][1].inertia_kg_m2
    full_i = cases["full_design_payload"][1].inertia_kg_m2
    x = np.arange(3)
    width = 0.36
    ax_inertia.bar(x - width / 2.0, dry_i, width, label="Dry", color=PALETTE["blue"], zorder=3)
    ax_inertia.bar(x + width / 2.0, full_i, width, label="Full payload", color=PALETTE["orange"], zorder=3)
    ax_inertia.set_xticks(x, inertias)
    ax_inertia.set_ylabel("Point-mass inertia about CG [kg·m²]")
    ax_inertia.set_title("Conceptual inertia response to payload", loc="left", fontsize=12.0)
    ax_inertia.legend(fontsize=7.8)
    style_axis(ax_inertia)

    dry_props = cases["dry_empty_basket"][1]
    full_props = cases["full_design_payload"][1]
    x_shift = full_props.cg_m[0] - dry_props.cg_m[0]
    _panel(info)
    _panel_heading(info, "DERIVED MASS CASES", "The payload is added at the configured basket location, not distributed artificially across the hulls.")
    y = _metric_table(
        info,
        [
            ("Dry mass", f"{dry_props.total_mass_kg:.3f} kg"),
            ("Payload increment", f"{full_props.total_mass_kg - dry_props.total_mass_kg:.3f} kg"),
            ("Full design mass", f"{full_props.total_mass_kg:.3f} kg"),
            ("CG forward shift", f"{x_shift:+.4f} m"),
            ("Dry capacity ratio", f"{geometry.capacity_mass_kg / dry_props.total_mass_kg:.2f}"),
            ("Full capacity ratio", f"{geometry.capacity_mass_kg / full_props.total_mass_kg:.2f}"),
        ],
        top=0.77,
    )
    _bullet_list(
        info,
        "MODEL BOUNDARY",
        [
            "This point-mass inertia is suitable for a transparent conceptual control model and sensitivity analysis.",
            "Distributed hull structure, added mass and hydrodynamic inertia are represented in later dynamics modules rather than being hidden in this Phase 02 calculation.",
        ],
        y=y - 0.045,
    )
    return export_figure(fig, path, dpi=320)


def _summary_markdown(
    geometry: CatamaranGeometry,
    rows: list[dict[str, object]],
    artifacts: Phase02Artifacts,
) -> str:
    dry, full = rows
    return f"""# AquaSkim-Sim | گزارش فنی فاز 02: معماری مکانیکی و خواص جرمی

## 1. هدف
این مرحله، آرایش مکانیکی مفهومی ربات کاتاماران، بودجهٔ جرم، مرکز جرم و تخمین اولیهٔ آبخور را با یک مدل پارامتریک قابل تکرار تولید می‌کند.

## 2. هندسهٔ انتخاب‌شده
| پارامتر | مقدار |
|---|---:|
| طول هر بدنه | {geometry.hull_length_m:.3f} m |
| عرض هر بدنه | {geometry.hull_width_m:.3f} m |
| ارتفاع هر بدنه | {geometry.hull_height_m:.3f} m |
| عرض کلی ربات | {geometry.overall_width_m:.3f} m |
| فاصلهٔ مرکز تا مرکز بدنه‌ها | {geometry.hull_spacing_center_m:.3f} m |
| عرض ورودی دهانهٔ جمع‌آوری | {geometry.collector_inlet_width_m:.3f} m |
| طول دهانهٔ جمع‌آوری | {geometry.collector_length_m:.3f} m |
| حجم اسمی سبد | {geometry.basket_volume_l:.1f} L |

## 3. مدل محاسباتی
حجم جابه‌جایی مفهومی از رابطهٔ زیر به‌دست می‌آید:

`V = 2 × L × B × H × C_shape`

جرم ظرفیت جابه‌جایی مفهومی:

`m_capacity = ρ_water × V`

در این طراحی، ظرفیت جابه‌جایی مفهومی برابر با **{geometry.capacity_mass_kg:.3f} kg** است. تخمین آبخور نیز از تقسیم جرم بر سطح مؤثر خط آب محاسبه می‌شود. این یک تقریب مرحلهٔ مفهومی است و تحلیل هیدرواستاتیکی رسمی در فاز بعدی انجام خواهد شد.

## 4. حالات بار
| حالت | جرم [kg] | CGx [m] | CGy [m] | CGz [m] | آبخور [m] | فری‌بورد [m] | ضریب ظرفیت |
|---|---:|---:|---:|---:|---:|---:|---:|
| سبد خالی | {float(dry['total_mass_kg']):.3f} | {float(dry['cg_x_m']):+.4f} | {float(dry['cg_y_m']):+.4f} | {float(dry['cg_z_m']):.4f} | {float(dry['draft_preview_m']):.4f} | {float(dry['freeboard_preview_m']):.4f} | {float(dry['displacement_capacity_ratio']):.2f} |
| بار طراحی کامل | {float(full['total_mass_kg']):.3f} | {float(full['cg_x_m']):+.4f} | {float(full['cg_y_m']):+.4f} | {float(full['cg_z_m']):.4f} | {float(full['draft_preview_m']):.4f} | {float(full['freeboard_preview_m']):.4f} | {float(full['displacement_capacity_ratio']):.2f} |

## 5. تفسیر مهندسی
- تقارن اجزای سمت چپ و راست باعث شده است `CGy ≈ 0` باشد؛ این موضوع برای پایداری جانبی کاتاماران مطلوب است.
- با اضافه‌شدن بار طراحی، مرکز جرم به اندازهٔ **{float(full['cg_x_m']) - float(dry['cg_x_m']):.4f} m** در جهت جلو جابه‌جا می‌شود. دلیل آن قرارگیری جرم زباله در محدودهٔ سبد است.
- در حالت بار کامل، فری‌بورد تخمینی **{float(full['freeboard_preview_m']):.4f} m** باقی می‌ماند.
- نسبت ظرفیت جابه‌جایی به جرم بار کامل برابر **{float(full['displacement_capacity_ratio']):.2f}** است؛ بنابراین طراحی مفهومی از نظر ظرفیت حجمی حاشیه دارد.
- ممان‌های اینرسی گزارش‌شده مبتنی بر تقریب جرم متمرکز هستند؛ در فازهای بعد، این مدل با توزیع جرم بدنه و جرم افزودهٔ سیال توسعه پیدا می‌کند.

## 6. کنترل کیفیت بصری
تمام شکل‌ها به‌صورت PNG با وضوح بالا برای گزارش Word و همچنین SVG برداری تولید شده‌اند. برچسب‌های متنی از هندسهٔ اصلی جدا شده‌اند تا هم‌پوشانی رخ ندهد.

## 7. فایل‌های تولیدشده
""" + "\n".join(f"- `{value}`" for value in artifacts.as_dict().values()) + "\n"


def run_phase02(config: ProjectConfiguration | None = None) -> Phase02Artifacts:
    """Regenerate the real Phase 02 artifacts from shared configuration.

    The function intentionally contains no hard-coded result tables.  Every
    numerical value is recalculated from ``config/base_parameters.yaml`` and
    the current geometry/mass-property helpers.
    """
    ensure_runtime_directories()
    project = config or load_base_configuration(apply_local_profile=False)
    geometry = CatamaranGeometry.from_config(project.data)
    cases = build_load_cases(project.data)
    dry_components = cases["dry_empty_basket"][0]
    case_rows = [_case_row(name, props, geometry) for name, (_, props) in cases.items()]

    artifacts = Phase02Artifacts(
        top_view=DIRECTORIES["figures"] / "phase02_mechanical_top_view.png",
        top_view_svg=DIRECTORIES["figures"] / "phase02_mechanical_top_view.svg",
        side_view=DIRECTORIES["figures"] / "phase02_mechanical_side_view.png",
        side_view_svg=DIRECTORIES["figures"] / "phase02_mechanical_side_view.svg",
        mass_distribution=DIRECTORIES["figures"] / "phase02_mass_distribution.png",
        mass_distribution_svg=DIRECTORIES["figures"] / "phase02_mass_distribution.svg",
        geometry_table=DIRECTORIES["tables"] / "phase02_geometry_summary.csv",
        mass_budget_table=DIRECTORIES["tables"] / "phase02_mass_budget.csv",
        mass_cases_table=DIRECTORIES["tables"] / "phase02_mass_cases.csv",
        component_key_table=DIRECTORIES["tables"] / "phase02_component_key.csv",
        summary_json=DIRECTORIES["logs"] / "phase02_mechanical_summary.json",
        summary_markdown=DIRECTORIES["reports"] / "phase02_mechanical_design_summary.md",
        visual_quality_manifest=DIRECTORIES["logs"] / "phase02_visual_quality_manifest.json",
    )

    exports = [
        _draw_top_view(geometry, dry_components, artifacts.top_view),
        _draw_side_view(geometry, cases, artifacts.side_view),
        _draw_mass_distribution(geometry, dry_components, cases, artifacts.mass_distribution),
    ]
    assert_export_quality(exports, min_width_px=3000, min_height_px=1800)

    _write_csv(artifacts.geometry_table, geometry.summary_rows())
    _write_csv(artifacts.mass_budget_table, mass_rows(dry_components))
    _write_csv(artifacts.mass_cases_table, case_rows)
    _write_csv(artifacts.component_key_table, _component_key(dry_components))

    summary = {
        "phase": "Phase 02 — Mechanical Architecture and Mass Properties",
        "configuration_file": relative_to_root(project.source_path),
        "geometry": {
            "hull_length_m": geometry.hull_length_m,
            "hull_width_m": geometry.hull_width_m,
            "hull_height_m": geometry.hull_height_m,
            "overall_width_m": geometry.overall_width_m,
            "capacity_mass_kg": geometry.capacity_mass_kg,
            "waterplane_area_m2": geometry.waterplane_area_m2,
        },
        "load_cases": {str(row["load_case"]): row for row in case_rows},
        "assumptions": [
            "Hull volume uses the versioned hull_shape_factor during conceptual design.",
            "Draft preview assumes a constant effective waterplane area.",
            "Inertia uses a point-mass approximation about the computed CG.",
            "Formal hydrostatic stability and added-mass modelling are outside Phase 02.",
        ],
        "visual_quality": {
            "phase": "Phase 02 visual quality gate",
            "quality_rule": {
                "minimum_png_width_px": 3000,
                "minimum_png_height_px": 1800,
                "formats": ["PNG (report-ready raster)", "SVG (vector)"],
                "label_policy": "Dense component names are moved to dedicated key tables; geometry uses indexed callouts.",
            },
            "exports": [export.as_dict() for export in exports],
        },
        "artifacts": artifacts.as_dict(),
    }
    artifacts.summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.visual_quality_manifest.write_text(json.dumps(summary["visual_quality"], ensure_ascii=False, indent=2), encoding="utf-8")
    artifacts.summary_markdown.write_text(_summary_markdown(geometry, case_rows, artifacts), encoding="utf-8")
    return artifacts


def print_phase02_summary(artifacts: Phase02Artifacts) -> None:
    print("=" * 72)
    print("AquaSkim-Sim | Phase 02 Mechanical Architecture")
    print("=" * 72)
    for name, value in artifacts.as_dict().items():
        print(f"{name:28}: {value}")
    print("=" * 72)
    print("[OK] Phase 02 figures, tables and summary have been generated from shared configuration.")


if __name__ == "__main__":
    generated = run_phase02()
    print_phase02_summary(generated)
