"""Phase 03 artifact generation: hydrostatics and transverse stability.

Every figure is deliberately designed for Word/PDF insertion.  Geometry is kept
clear of explanatory prose; panels use manual fixed-layout metric cells and
wrapped text rather than automatic Matplotlib tables, which prevents clipping
and overlap across Windows, SVG and PNG renderers.
"""
from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from textwrap import fill

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Rectangle, FancyBboxPatch
import numpy as np

from aquaskim.config import ProjectConfiguration, load_base_configuration
from aquaskim.geometry import CatamaranGeometry
from aquaskim.hydrostatics import CatamaranHydrostatics, HeelState, HydrostaticCase, HydrostaticSettings
from aquaskim.mass_properties import build_load_cases
from aquaskim.paths import DIRECTORIES, ensure_runtime_directories, relative_to_root
from aquaskim.visual_quality import (
    PALETTE,
    FigureExport,
    add_figure_header,
    apply_engineering_style,
    assert_export_quality,
    export_figure,
    style_axis,
)


@dataclass(frozen=True)
class Phase03Artifacts:
    hydrostatics_dashboard: Path
    hydrostatics_dashboard_svg: Path
    stability_curves: Path
    stability_curves_svg: Path
    heeling_cross_sections: Path
    heeling_cross_sections_svg: Path
    payload_envelope: Path
    payload_envelope_svg: Path
    hydrostatic_cases_table: Path
    stability_curve_table: Path
    payload_envelope_table: Path
    acceptance_checks_table: Path
    summary_json: Path
    summary_markdown: Path
    visual_quality_manifest: Path

    def as_dict(self) -> dict[str, str]:
        return {name: relative_to_root(path) for name, path in self.__dict__.items()}


def _write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"Cannot write empty CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def _case_label(case_name: str) -> str:
    return "Dry / empty basket" if case_name == "dry_empty_basket" else "Full design payload"


def _panel(ax: plt.Axes) -> None:
    ax.set_axis_off()
    ax.set_xlim(0.0, 1.0)
    ax.set_ylim(0.0, 1.0)
    ax.add_patch(
        FancyBboxPatch(
            (0.025, 0.03), 0.95, 0.94,
            boxstyle="round,pad=0.018,rounding_size=0.02",
            facecolor="#F8FBFD", edgecolor=PALETTE["grid"], linewidth=1.0,
        )
    )


def _panel_heading(ax: plt.Axes, heading: str, subtitle: str | None = None) -> None:
    ax.text(0.08, 0.92, heading, fontsize=13.0, fontweight="bold", color=PALETTE["navy"], va="top")
    if subtitle:
        ax.text(0.08, 0.87, fill(subtitle, 54), fontsize=8.45, color=PALETTE["gray"], va="top", linespacing=1.35)


def _metric_grid(
    ax: plt.Axes,
    rows: list[tuple[str, str, str]],
    *,
    top: float,
    height: float,
    headers: tuple[str, str, str] = ("Metric", "Dry", "Full"),
) -> None:
    """Draw a fixed metric table without renderer-dependent Table behavior."""
    x0, width = 0.08, 0.84
    cols = (0.48, 0.26, 0.26)
    row_h = height / (len(rows) + 1)
    current_y = top
    for row_idx, values in enumerate([headers, *rows]):
        y = current_y - row_h
        cursor = x0
        for col_idx, (fraction, value) in enumerate(zip(cols, values)):
            face = PALETTE["navy"] if row_idx == 0 else (PALETTE["gray_light"] if col_idx == 0 else PALETTE["white"])
            ax.add_patch(Rectangle((cursor, y), width * fraction, row_h, facecolor=face, edgecolor=PALETTE["grid"], linewidth=0.65))
            ax.text(
                cursor + (0.012 if col_idx == 0 else width * fraction / 2.0),
                y + row_h / 2.0,
                value,
                ha="left" if col_idx == 0 else "center",
                va="center",
                fontsize=7.7 if row_idx else 7.5,
                fontweight="bold" if row_idx == 0 else "normal",
                color=PALETTE["white"] if row_idx == 0 else PALETTE["gray_dark"],
            )
            cursor += width * fraction
        current_y = y


def _bullet_block(ax: plt.Axes, heading: str, bullets: list[str], *, y: float, width: int = 52) -> float:
    ax.text(0.08, y, heading, fontsize=10.3, fontweight="bold", color=PALETTE["navy"], va="top")
    current = y - 0.045
    for bullet in bullets:
        wrapped = fill(bullet, width=width)
        ax.text(0.095, current, "• " + wrapped.replace("\n", "\n  "), fontsize=8.45, color=PALETTE["gray_dark"], va="top", linespacing=1.42)
        line_count = wrapped.count("\n") + 1
        current -= 0.032 * line_count + 0.018
    return current


def _draw_transverse_section(
    ax: plt.Axes,
    hydro: CatamaranHydrostatics,
    case: HydrostaticCase,
    heel_deg: float,
    *,
    compact: bool = False,
    show_legend: bool = True,
) -> HeelState:
    """Draw a transverse twin-hull section with accurate waterline data."""
    state = hydro.heel_state(case, heel_deg)
    g = hydro.geometry
    phi = np.deg2rad(heel_deg)
    eff_width = g.hull_width_m * g.waterplane_shape_factor
    for center_y in g.hull_centerlines_y_m():
        y_left = center_y - eff_width / 2.0
        y_right = center_y + eff_width / 2.0
        ax.add_patch(Rectangle((y_left, 0.0), eff_width, g.hull_height_m, fill=False, linewidth=1.8, edgecolor=PALETTE["navy"], zorder=4))
        y_line = np.linspace(y_left, y_right, 121)
        depth = np.clip(state.equilibrium_draft_m + y_line * np.tan(phi), 0.0, g.hull_height_m)
        ax.fill_between(y_line, 0.0, depth, color=PALETTE["sky"], alpha=0.9, zorder=1)
        ax.plot(y_line, depth, color=PALETTE["blue"], linewidth=1.55, zorder=5)

    cg_y = -case.kg_m * np.sin(phi)
    cg_z = case.kg_m * np.cos(phi)
    cb_y = state.cb_y_m * np.cos(phi) - state.cb_z_m * np.sin(phi)
    cb_z = state.cb_y_m * np.sin(phi) + state.cb_z_m * np.cos(phi)
    ax.scatter([cg_y], [cg_z], marker="x", s=62, linewidths=2.0, color=PALETTE["orange"], label="CG" if show_legend else None, zorder=7)
    ax.scatter([cb_y], [cb_z], marker="o", s=36, color=PALETTE["green"], label="CB" if show_legend else None, zorder=7)
    ax.axhline(0.0, color=PALETTE["gray_dark"], linewidth=0.8)
    ax.set_xlim(-0.29, 0.29)
    ax.set_ylim(-0.015, 0.205)
    ax.set_xlabel("y [m] — port positive", fontsize=9.0 if compact else 10.0)
    ax.set_ylabel("z [m]", fontsize=9.0 if compact else 10.0)
    style_axis(ax)
    if compact:
        ax.set_aspect("auto")
    else:
        ax.set_aspect("equal", adjustable="box")
    if show_legend:
        ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.20), ncol=2, fontsize=8)
    return state


def _draw_hydrostatics_dashboard(hydro: CatamaranHydrostatics, cases: dict[str, HydrostaticCase], output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 10.0), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.38, 0.92], left=0.055, right=0.955, bottom=0.075, top=0.875, wspace=0.14, hspace=0.34)
    dry_ax = fig.add_subplot(grid[0, 0])
    full_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Hydrostatic Equilibrium", "Phase 03 • Calm-water hydrostatics • Cross-section model • All dimensions in metres")
    dry_state = _draw_transverse_section(dry_ax, hydro, cases["dry_empty_basket"], 0.0)
    full_state = _draw_transverse_section(full_ax, hydro, cases["full_design_payload"], 0.0)
    dry_ax.set_title("Dry / empty basket — equilibrium", loc="left", fontsize=12.5)
    full_ax.set_title("Full design payload — equilibrium", loc="left", fontsize=12.5)

    _panel(info)
    _panel_heading(info, "HYDROSTATIC DESIGN CHECK", "Formal small-angle terms are evaluated from the configured effective waterplane.")
    rows = [
        ("Mass [kg]", f"{cases['dry_empty_basket'].total_mass_kg:.3f}", f"{cases['full_design_payload'].total_mass_kg:.3f}"),
        ("Draft T [m]", f"{dry_state.equilibrium_draft_m:.4f}", f"{full_state.equilibrium_draft_m:.4f}"),
        ("Freeboard [m]", f"{cases['dry_empty_basket'].freeboard_m:.4f}", f"{cases['full_design_payload'].freeboard_m:.4f}"),
        ("KB [m]", f"{cases['dry_empty_basket'].kb_m:.4f}", f"{cases['full_design_payload'].kb_m:.4f}"),
        ("BM [m]", f"{cases['dry_empty_basket'].bm_m:.4f}", f"{cases['full_design_payload'].bm_m:.4f}"),
        ("KG [m]", f"{cases['dry_empty_basket'].kg_m:.4f}", f"{cases['full_design_payload'].kg_m:.4f}"),
        ("GM [m]", f"{cases['dry_empty_basket'].gm_m:.4f}", f"{cases['full_design_payload'].gm_m:.4f}"),
    ]
    _metric_grid(info, rows, top=0.81, height=0.31)
    info.text(0.08, 0.44, "MODEL BASIS", fontsize=10.3, fontweight="bold", color=PALETTE["navy"], va="top")
    basis = (
        "Fresh water density is 1000 kg/m³. Each hull is represented by an effective waterplane strip. "
        "Static equilibrium follows Δ = ρ·∇; the present conceptual model uses KB = 0.5·T, BM = Iₜ/∇, and GM = KB + BM − KG."
    )
    info.text(0.09, 0.405, fill(basis, width=57), fontsize=8.25, color=PALETTE["gray_dark"], va="top", linespacing=1.40)
    info.text(0.08, 0.245, "INTERPRETATION", fontsize=10.3, fontweight="bold", color=PALETTE["navy"], va="top")
    interpretation = (
        "Both load cases have positive GM. The full-payload condition has lower freeboard and lower GM, so it is retained as the governing case. "
        "Finite-heel waterline, emergence and righting-moment checks are shown in the next figures."
    )
    info.text(0.09, 0.21, fill(interpretation, width=57), fontsize=8.25, color=PALETTE["gray_dark"], va="top", linespacing=1.40)
    return export_figure(fig, output_path, dpi=320)


def _draw_stability_curves(hydro: CatamaranHydrostatics, cases: dict[str, HydrostaticCase], curves: dict[str, list[HeelState]], output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 10.0), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.42, 0.88], left=0.055, right=0.955, bottom=0.085, top=0.875, wspace=0.16, hspace=0.32)
    gz_ax = fig.add_subplot(grid[0, 0])
    rm_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Transverse Stability Curves", "Phase 03 • Nonlinear strip integration with a small-angle GM reference • Positive heel = port-down")

    styles = [("dry_empty_basket", PALETTE["blue"], "-"), ("full_design_payload", PALETTE["green"], "--")]
    for case_name, color, linestyle in styles:
        curve = curves[case_name]
        heel = [s.heel_deg for s in curve]
        gz_ax.plot(heel, [s.gz_nonlinear_m for s in curve], color=color, linewidth=2.25, linestyle=linestyle, label=f"{_case_label(case_name)} — nonlinear")
        gz_ax.plot(heel, [s.gz_linear_m for s in curve], color=color, linewidth=1.05, linestyle=":", label=f"{_case_label(case_name)} — GM reference")
        rm_ax.plot(heel, [s.righting_moment_n_m for s in curve], color=color, linewidth=2.25, linestyle=linestyle, label=_case_label(case_name))
    for axis in (gz_ax, rm_ax):
        axis.axvspan(0.0, hydro.settings.linear_model_valid_to_deg, color=PALETTE["green_light"], alpha=0.48, zorder=0)
        axis.axvline(hydro.settings.operational_heel_limit_deg, color=PALETTE["orange"], linewidth=1.25, linestyle="--")
        axis.set_xlim(0.0, hydro.settings.analysis_heel_max_deg)
        style_axis(axis)
    gz_ax.set_title("Righting arm GZ", loc="left", fontsize=12.5)
    gz_ax.set_xlabel("Heel angle [deg]")
    gz_ax.set_ylabel("GZ [m]")
    gz_ax.legend(loc="upper left", fontsize=7.45, ncol=2)
    rm_ax.set_title("Righting moment", loc="left", fontsize=12.5)
    rm_ax.set_xlabel("Heel angle [deg]")
    rm_ax.set_ylabel("Righting moment [N·m]")
    rm_ax.legend(loc="upper left", fontsize=8.0)

    _panel(info)
    _panel_heading(info, "STABILITY INTERPRETATION", "The shaded region is the intended linear-design range. The 5° orange line is the operating heel constraint for later control design.")
    data_rows: list[tuple[str, str, str]] = []
    # Use compact but readable rows; split load-case values into two separate rows.
    for case_name in ("dry_empty_basket", "full_design_payload"):
        case = cases[case_name]
        operating = hydro.operating_state(case)
        emergence = hydro.first_emergence_angle_deg(curves[case_name])
        fb_limit = hydro.first_freeboard_limit_angle_deg(curves[case_name])
        data_rows.append((
            "Dry case" if case_name == "dry_empty_basket" else "Full payload",
            f"GM {case.gm_m:.3f} m",
            f"M@5° {operating.righting_moment_n_m:.2f} N·m",
        ))
        data_rows.append((
            "Immersion markers",
            "emergence " + ("not reached" if emergence is None else f"{emergence:.2f}°"),
            "FB limit " + ("not reached" if fb_limit is None else f"{fb_limit:.2f}°"),
        ))
    _metric_grid(info, data_rows, top=0.79, height=0.19, headers=("Case / metric", "Value 1", "Value 2"))
    info.text(0.08, 0.55, "READING THE CURVES", fontsize=10.3, fontweight="bold", color=PALETTE["navy"], va="top")
    reading = (
        "Solid lines are finite-heel results from the two-hull strip model; dotted lines are the GM·sin(φ) reference. "
        "Beyond the green range, the finite-heel result is the design reference. Emergence marks the first near-dry strip on the lifted hull."
    )
    info.text(0.09, 0.515, fill(reading, width=54), fontsize=8.2, color=PALETTE["gray_dark"], va="top", linespacing=1.40)
    info.text(0.08, 0.29, "ENGINEERING DECISION", fontsize=10.3, fontweight="bold", color=PALETTE["navy"], va="top")
    decision = (
        f"The full-payload case has the lower initial GM ({cases['full_design_payload'].gm_m:.3f} m) and remains governing. "
        "Normal manoeuvres will be constrained to the 5° operating-heel envelope until dynamic roll modelling is implemented."
    )
    info.text(0.09, 0.255, fill(decision, width=54), fontsize=8.2, color=PALETTE["gray_dark"], va="top", linespacing=1.40)
    return export_figure(fig, output_path, dpi=320)


def _draw_heeling_cross_sections(hydro: CatamaranHydrostatics, full_case: HydrostaticCase, output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 8.0), constrained_layout=False)
    grid = GridSpec(1, 4, figure=fig, width_ratios=[1.0, 1.0, 1.0, 1.05], left=0.05, right=0.955, bottom=0.14, top=0.83, wspace=0.25)
    angles = (0.0, hydro.settings.operational_heel_limit_deg, 10.0)
    for index, heel in enumerate(angles):
        ax = fig.add_subplot(grid[0, index])
        state = _draw_transverse_section(ax, hydro, full_case, heel, compact=True, show_legend=(index == 0))
        ax.set_title(f"Heel = {heel:.1f}°", fontsize=11.5, loc="left")
        ax.text(0.02, 0.96, f"minimum freeboard = {state.min_freeboard_m:.3f} m", transform=ax.transAxes, ha="left", va="top", fontsize=7.7, color=PALETTE["gray_dark"], bbox={"boxstyle": "round,pad=0.22", "facecolor": PALETTE["white"], "edgecolor": PALETTE["grid"], "alpha": 0.96})
    info = fig.add_subplot(grid[0, 3])
    _panel(info)
    _panel_heading(info, "FULL-LOAD HEEL VIEW", "Full payload governs the transverse-stability review.")
    _bullet_block(info, "WHAT IS SHOWN", [
        "At each angle the equilibrium water level is solved so total displaced volume stays equal to the full design displacement.",
        "The local waterline is clipped at the keel and hull height, exposing low freeboard or partial emergence directly.",
        "The 10° view is diagnostic only. It is not a normal mission condition.",
    ], y=0.75, width=43)
    _bullet_block(info, "DRAWING NOTE", [
        "The section panels use vertically expanded schematic scaling to keep waterline changes readable in the report. All displayed waterline values and axes remain numeric.",
    ], y=0.27, width=43)
    fig.text(0.055, 0.965, "AquaSkim-Sim | Full-Payload Heeling Cross-Sections", ha="left", va="top", fontsize=17, fontweight="bold", color=PALETTE["navy"])
    fig.text(0.055, 0.932, "Phase 03 • Positive heel = port-down • Finite-heel equilibrium waterline", ha="left", va="top", fontsize=9.5, color=PALETTE["gray"])
    fig.lines.append(plt.Line2D([0.055, 0.95], [0.918, 0.918], transform=fig.transFigure, color=PALETTE["cyan"], linewidth=1.0))
    return export_figure(fig, output_path, dpi=320)


def _draw_payload_envelope(hydro: CatamaranHydrostatics, payload_rows: list[dict[str, float]], output_path: Path) -> FigureExport:
    apply_engineering_style()
    fig = plt.figure(figsize=(16.0, 9.2), constrained_layout=False)
    grid = GridSpec(2, 2, figure=fig, width_ratios=[1.42, 0.88], left=0.055, right=0.955, bottom=0.085, top=0.875, wspace=0.15, hspace=0.34)
    draft_ax = fig.add_subplot(grid[0, 0])
    gm_ax = fig.add_subplot(grid[1, 0])
    info = fig.add_subplot(grid[:, 1])
    add_figure_header(fig, "AquaSkim-Sim | Payload Hydrostatic Envelope", "Phase 03 • Basket payload sweep from empty to design load • Calm-water equilibrium")
    payload = [row["payload_kg"] for row in payload_rows]
    draft_ax.plot(payload, [row["draft_m"] for row in payload_rows], color=PALETTE["blue"], linewidth=2.25, label="Draft")
    draft_ax.plot(payload, [row["freeboard_m"] for row in payload_rows], color=PALETTE["green"], linewidth=2.25, linestyle="--", label="Freeboard")
    draft_ax.axhline(hydro.settings.minimum_freeboard_m, linewidth=1.1, linestyle=":", color=PALETTE["orange"], label="Minimum freeboard")
    draft_ax.set_xlabel("Collected payload [kg]")
    draft_ax.set_ylabel("Length [m]")
    draft_ax.set_title("Draft and freeboard", loc="left", fontsize=12.5)
    draft_ax.legend(loc="center right", fontsize=8.3)
    style_axis(draft_ax)
    gm_ax.plot(payload, [row["GM_m"] for row in payload_rows], color=PALETTE["blue"], linewidth=2.25, label="GM")
    gm_ax.axhline(hydro.settings.minimum_gm_m, linewidth=1.1, linestyle=":", color=PALETTE["orange"], label="Minimum GM")
    gm_ax.set_xlabel("Collected payload [kg]")
    gm_ax.set_ylabel("GM [m]")
    gm_ax.set_title("Initial transverse stability", loc="left", fontsize=12.5)
    gm_ax.legend(loc="upper right", fontsize=8.3)
    style_axis(gm_ax)

    _panel(info)
    _panel_heading(info, "PAYLOAD DESIGN ENVELOPE", "Payload is swept continuously from an empty basket to the configured design payload.")
    final = payload_rows[-1]
    rows = [
        ("Payload range", "0.00 kg", f"{payload[-1]:.2f} kg"),
        ("Full-load draft", "", f"{final['draft_m']:.4f} m"),
        ("Full-load freeboard", "", f"{final['freeboard_m']:.4f} m"),
        ("Full-load GM", "", f"{final['GM_m']:.4f} m"),
        ("Minimum freeboard", "rule", f"≥ {hydro.settings.minimum_freeboard_m:.3f} m"),
        ("Minimum GM", "rule", f"≥ {hydro.settings.minimum_gm_m:.3f} m"),
    ]
    _metric_grid(info, rows, top=0.80, height=0.255, headers=("Metric", "Reference", "Value"))
    _bullet_block(info, "WHY THIS SWEEP MATTERS", [
        "Collected debris increases total displacement and moves CG toward the basket location.",
        "The sweep confirms whether the selected payload limit remains inside the freeboard and initial-stability design rules.",
        "The autonomy agent will use the design payload limit as a return-to-home condition in a later phase.",
    ], y=0.47, width=52)
    return export_figure(fig, output_path, dpi=320)


def _acceptance_rows(hydro: CatamaranHydrostatics, cases: dict[str, HydrostaticCase]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for name, case in cases.items():
        operating = hydro.operating_state(case)
        rows.extend([
            {"load_case": name, "criterion": "Positive initial GM", "value": case.gm_m, "threshold": hydro.settings.minimum_gm_m, "unit": "m", "status": "PASS" if case.gm_m >= hydro.settings.minimum_gm_m else "FAIL"},
            {"load_case": name, "criterion": "Static freeboard at zero heel", "value": case.freeboard_m, "threshold": hydro.settings.minimum_freeboard_m, "unit": "m", "status": "PASS" if case.freeboard_m >= hydro.settings.minimum_freeboard_m else "FAIL"},
            {"load_case": name, "criterion": f"Minimum freeboard at {hydro.settings.operational_heel_limit_deg:.1f} deg", "value": operating.min_freeboard_m, "threshold": hydro.settings.minimum_freeboard_m, "unit": "m", "status": "PASS" if operating.min_freeboard_m >= hydro.settings.minimum_freeboard_m else "FAIL"},
            {"load_case": name, "criterion": f"Positive righting moment at {hydro.settings.operational_heel_limit_deg:.1f} deg", "value": operating.righting_moment_n_m, "threshold": 0.0, "unit": "N m", "status": "PASS" if operating.righting_moment_n_m > 0.0 else "FAIL"},
        ])
    return rows


def _write_summary(path: Path, hydro: CatamaranHydrostatics, cases: dict[str, HydrostaticCase], curves: dict[str, list[HeelState]], artifacts: Phase03Artifacts) -> None:
    full = cases["full_design_payload"]
    operating = hydro.operating_state(full)
    emergence = hydro.first_emergence_angle_deg(curves["full_design_payload"])
    fb_limit = hydro.first_freeboard_limit_angle_deg(curves["full_design_payload"])
    content = f"""# AquaSkim-Sim | Phase 03 — Hydrostatics and Transverse Stability

## Purpose
This phase replaces the Phase 02 draft preview with a documented calm-water hydrostatic model. It evaluates equilibrium draft, freeboard, KB, BM, KG, GM and finite-heel righting response for dry and full-payload conditions.

## Governing full-payload case

| Quantity | Value |
|---|---:|
| Total mass | {full.total_mass_kg:.3f} kg |
| Draft | {full.draft_m:.4f} m |
| Freeboard | {full.freeboard_m:.4f} m |
| KB | {full.kb_m:.4f} m |
| BM | {full.bm_m:.4f} m |
| KG | {full.kg_m:.4f} m |
| GM | {full.gm_m:.4f} m |
| GZ at {hydro.settings.operational_heel_limit_deg:.1f}° | {operating.gz_nonlinear_m:.4f} m |
| Righting moment at {hydro.settings.operational_heel_limit_deg:.1f}° | {operating.righting_moment_n_m:.3f} N·m |
| First local emergence | {"not reached" if emergence is None else f"{emergence:.2f}°"} |
| First minimum-freeboard threshold crossing | {"not reached" if fb_limit is None else f"{fb_limit:.2f}°"} |

## Modelling basis

1. Fresh-water density is `1000 kg/m³`.
2. Two effective waterplane strips represent the twin hulls.
3. Initial stability uses `GM = KB + BM − KG` and `BM = I_T / ∇`.
4. Finite heel is evaluated through numerical strip integration with constant displacement.
5. Local draft is clipped between keel and hull height so partial emergence and low freeboard are visible.

## Scope limits

- Positive acceptance checks show consistency with the configured conceptual model; they do not certify sea-worthiness.
- The phase excludes waves, CFD, wind, speed-dependent lift, added mass, viscous roll damping and transient roll dynamics.
- The effective-waterplane approximation will be refined with CAD-derived hydrostatics in a later design iteration.

## Generated artifacts
{chr(10).join(f"- `{value}`" for value in artifacts.as_dict().values())}
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def run_phase03(config: ProjectConfiguration | None = None) -> Phase03Artifacts:
    ensure_runtime_directories()
    project_config = config or load_base_configuration()
    geometry = CatamaranGeometry.from_config(project_config.data)
    settings = HydrostaticSettings.from_config(project_config.data)
    hydro = CatamaranHydrostatics(geometry, settings)
    load_cases = build_load_cases(project_config.data)
    cases = {name: hydro.case_from_mass_properties(name, props) for name, (_, props) in load_cases.items()}
    curves = {name: hydro.heel_curve(case) for name, case in cases.items()}
    dry_components, dry_properties = load_cases["dry_empty_basket"]
    basket = next(component for component in dry_components if component.name == "basket")
    payload_rows = hydro.payload_envelope(dry_properties, basket.position_m, float(project_config.data["mechanical"]["geometry"]["design_payload_kg"]))
    acceptance = _acceptance_rows(hydro, cases)

    dashboard = DIRECTORIES["figures"] / "phase03_hydrostatics_dashboard.png"
    curves_figure = DIRECTORIES["figures"] / "phase03_stability_curves.png"
    heeling_figure = DIRECTORIES["figures"] / "phase03_heeling_cross_sections.png"
    envelope_figure = DIRECTORIES["figures"] / "phase03_payload_envelope.png"
    hydro_cases_table = DIRECTORIES["tables"] / "phase03_hydrostatic_cases.csv"
    stability_table = DIRECTORIES["tables"] / "phase03_stability_curve.csv"
    payload_table = DIRECTORIES["tables"] / "phase03_payload_envelope.csv"
    acceptance_table = DIRECTORIES["tables"] / "phase03_acceptance_checks.csv"
    summary_json = DIRECTORIES["logs"] / "phase03_hydrostatic_summary.json"
    summary_markdown = DIRECTORIES["reports"] / "phase03_hydrostatics_and_stability_summary.md"
    visual_quality = DIRECTORIES["logs"] / "phase03_visual_quality_manifest.json"

    artifacts = Phase03Artifacts(
        hydrostatics_dashboard=dashboard, hydrostatics_dashboard_svg=dashboard.with_suffix(".svg"),
        stability_curves=curves_figure, stability_curves_svg=curves_figure.with_suffix(".svg"),
        heeling_cross_sections=heeling_figure, heeling_cross_sections_svg=heeling_figure.with_suffix(".svg"),
        payload_envelope=envelope_figure, payload_envelope_svg=envelope_figure.with_suffix(".svg"),
        hydrostatic_cases_table=hydro_cases_table, stability_curve_table=stability_table,
        payload_envelope_table=payload_table, acceptance_checks_table=acceptance_table,
        summary_json=summary_json, summary_markdown=summary_markdown, visual_quality_manifest=visual_quality,
    )

    exports = [
        _draw_hydrostatics_dashboard(hydro, cases, dashboard),
        _draw_stability_curves(hydro, cases, curves, curves_figure),
        _draw_heeling_cross_sections(hydro, cases["full_design_payload"], heeling_figure),
        _draw_payload_envelope(hydro, payload_rows, envelope_figure),
    ]
    assert_export_quality(exports, min_width_px=4500, min_height_px=2400)
    _write_csv(hydro_cases_table, [case.as_row() for case in cases.values()])
    _write_csv(stability_table, [state.as_row(case_name) for case_name, curve in curves.items() for state in curve])
    _write_csv(payload_table, payload_rows)
    _write_csv(acceptance_table, acceptance)

    summary = {
        "phase": "Phase 03 — Hydrostatics and Transverse Stability",
        "configuration_file": relative_to_root(project_config.source_path),
        "settings": settings.__dict__,
        "hydrostatic_cases": {name: case.as_row() for name, case in cases.items()},
        "acceptance_checks": acceptance,
        "assumptions": [
            "Calm fresh water with density 1000 kg/m^3.",
            "Two identical effective waterplane strips represent the twin hulls.",
            "Initial stability uses KB, BM, KG and GM small-angle hydrostatics.",
            "Finite heel is evaluated by numerical strip integration with constant displacement.",
            "No CFD, waves, added mass, dynamic roll damping or speed-dependent effects in Phase 03.",
        ],
        "artifacts": artifacts.as_dict(),
    }
    summary_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    visual_quality.write_text(json.dumps({
        "phase": "Phase 03 visual quality gate",
        "quality_rule": {
            "minimum_png_width_px": 4500,
            "minimum_png_height_px": 2400,
            "formats": ["PNG (report-ready raster)", "SVG (vector)"],
            "label_policy": "Long explanations are confined to separate information panels; geometry panes use compact markers only.",
        },
        "exports": [export.as_dict() for export in exports],
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    _write_summary(summary_markdown, hydro, cases, curves, artifacts)
    return artifacts


def print_phase03_summary(artifacts: Phase03Artifacts) -> None:
    print("=" * 72)
    print("AquaSkim-Sim | Phase 03 Hydrostatics and Stability")
    print("=" * 72)
    for name, path in artifacts.as_dict().items():
        print(f"{name:28}: {path}")
    print("=" * 72)
    print("[OK] Phase 03 hydrostatics, stability curves, visual QA and reports generated.")
